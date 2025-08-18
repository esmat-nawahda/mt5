#!/usr/bin/env python3
"""
DeepSeek × MT5 Multi-Pair Autotrader with News Guard + CSV Logging
- Pairs: XAUUSD, EURUSD, GBPUSD, BTCUSD
- Random re-check 3–5 minutes
- Prioritize most confident pair from DeepSeek; do NOT replace an open pair until TP/SL
- Block trading 60 min before/after high-impact news (ForexFactory scraper)
- CSV logging of decisions & executions with WIN/LOSS column
"""

import os, time, random, logging, json, uuid
import MetaTrader5 as mt5
import requests, yaml
from dotenv import load_dotenv
from news_filter import is_blocked_now
from trading_logger import init_logger, log_trade

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

PAIRS = os.getenv("PAIRS", "XAUUSD,EURUSD,GBPUSD,BTCUSD").split(",")
LLM_URL = os.getenv("LLM_URL")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-trader")
LLM_KEY = os.getenv("LLM_API_KEY")
MIN_RECHECK = int(os.getenv("MIN_RECHECK_MINUTES", "3"))
MAX_RECHECK = int(os.getenv("MAX_RECHECK_MINUTES", "5"))
VOLUME = float(os.getenv("VOLUME", "1.00"))
DEVIATION = int(os.getenv("DEVIATION", "30"))
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "78"))

MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")

def mt5_init():
    if not mt5.initialize(login=MT5_LOGIN or None, password=MT5_PASSWORD or None, server=MT5_SERVER or None):
        raise RuntimeError(f"MT5 init failed: {mt5.last_error()}")
    ai = mt5.account_info()
    if not ai: raise RuntimeError("MT5 account_info failed")
    logging.info(f"MT5 connected | {ai.login} | Equity {ai.equity}")

def ensure_symbol(sym: str):
    si = mt5.symbol_info(sym)
    if si is None:
        raise RuntimeError(f"Unknown symbol {sym}")
    if not si.visible:
        if not mt5.symbol_select(sym, True):
            raise RuntimeError(f"Cannot select {sym}")

def fetch_snapshot(symbol: str) -> dict:
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 100)
    if rates is None or len(rates) < 1:
        raise RuntimeError(f"No rates for {symbol}")
    last = rates[-1]
    return {"symbol": symbol, "last_price": float(last["close"])}

def open_positions_map() -> dict:
    positions = mt5.positions_get()
    if positions is None: return {}
    return {p.symbol: p for p in positions}

def open_trade(symbol: str, action: str, sl: float, tp: float):
    ensure_symbol(symbol)
    tick = mt5.symbol_info_tick(symbol)
    if action.upper() == "BUY":
        price = tick.ask; otype = mt5.ORDER_TYPE_BUY
    elif action.upper() == "SELL":
        price = tick.bid; otype = mt5.ORDER_TYPE_SELL
    else:
        return None
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": VOLUME,
        "type": otype,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": DEVIATION,
        "magic": 991337,
        "comment": "DeepSeek MultiPair",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    res = mt5.order_send(req)
    logging.info(f"Opened {action} {symbol} | {res}")
    return res

def update_sl_tp(position, new_sl: float, new_tp: float):
    req = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": position.symbol,
        "sl": new_sl,
        "tp": new_tp,
        "position": position.ticket,
    }
    res = mt5.order_send(req)
    logging.info(f"Update SL/TP {position.symbol} → SL {new_sl} | TP {new_tp} | {res}")
    return res

def deepseek_analyze(market_snapshots: dict) -> dict:
    headers = {"Authorization": f"Bearer {LLM_KEY}", "Content-Type":"application/json"}
    user_prompt = f"""
Return STRICT YAML for these pairs {PAIRS}.
Schema:
pairs:
  - symbol: "XAUUSD|EURUSD|GBPUSD|BTCUSD"
    action: "BUY|SELL|NO TRADE"
    confidence: <float percent>
    entry: <float, required if BUY/SELL>
    sl: <float, required if BUY/SELL>
    tp: <float, required if BUY/SELL>

Market snapshots:
{json.dumps(market_snapshots, indent=2)}
"""
    payload = {
        "model": LLM_MODEL,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": "You are a trading AI. Return STRICT YAML only."},
            {"role": "user", "content": user_prompt}
        ]
    }
    r = requests.post(LLM_URL, headers=headers, json=payload, timeout=20)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    
    # Strip markdown code blocks if present
    if content.startswith("```"):
        lines = content.split('\n')
        # Remove first line (```yaml or similar)
        if lines[0].startswith("```"):
            lines = lines[1:]
        # Remove last line if it's just ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = '\n'.join(lines)
    
    try:
        parsed = yaml.safe_load(content)
        return parsed
    except Exception as e:
        raise ValueError(f"DeepSeek returned non-YAML or invalid YAML:\\n{content}") from e

def validate_pairs_block(sig: dict):
    required = set(p.strip().upper() for p in PAIRS)
    got = set(p.get("symbol","").upper() for p in sig.get("pairs", []))
    missing = required - got
    if missing:
        raise ValueError(f"Missing pairs in DeepSeek response: {missing}")

def cycle_once():
    snapshots = {p: fetch_snapshot(p) for p in PAIRS}
    sig = deepseek_analyze(snapshots)
    validate_pairs_block(sig)
    ranked = sorted(sig["pairs"], key=lambda x: x.get("confidence", 0), reverse=True)
    open_pos = open_positions_map()

    for s in ranked:
        sym = s.get("symbol").upper()
        action = (s.get("action") or "NO TRADE").upper()
        conf = float(s.get("confidence", 0))

        # Log decision (even if we don't trade)
        decision_id = str(uuid.uuid4())[:8]
        reason = ""

        if conf < MIN_CONFIDENCE or action == "NO TRADE":
            reason = f"Below threshold or NO_TRADE (conf={conf}%, action={action})"
            log_trade(decision_id, sym, action, conf, "", "", "", status="SKIPPED", reason=reason)
            continue

        blocked, reason_news = is_blocked_now(sym)
        if blocked:
            log_trade(decision_id, sym, action, conf, "", "", "", status="BLOCKED", reason=reason_news)
            continue

        if sym in open_pos:
            # Keep running, update SL/TP if provided
            pos = open_pos[sym]
            if "sl" in s and "tp" in s and s["sl"] and s["tp"]:
                update_sl_tp(pos, float(s["sl"]), float(s["tp"]))
                log_trade(decision_id, sym, action, conf, "", s["sl"], s["tp"], status="UPDATED", reason="Updated SL/TP")
            else:
                log_trade(decision_id, sym, action, conf, "", "", "", status="SKIPPED", reason="Already open")
            continue

        # Open new position for top eligible signal
        entry = float(s["entry"]); sl = float(s["sl"]); tp = float(s["tp"])
        res = open_trade(sym, action, sl, tp)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            trade_id = str(res.order or res.deal or decision_id)
            log_trade(trade_id, sym, action, conf, entry, sl, tp, status="OPEN", reason="Order executed")
        else:
            log_trade(decision_id, sym, action, conf, entry, sl, tp, status="ERROR", reason=f"order_send failed: {getattr(res,'retcode',None)}")
        break  # only one new position per cycle

def main():
    init_logger()
    # Try connecting without credentials first (use already logged-in terminal)
    if not mt5.initialize():
        # If that fails, try with credentials
        if not mt5.initialize(login=MT5_LOGIN or None, password=MT5_PASSWORD or None, server=MT5_SERVER or None):
            raise RuntimeError(f"MT5 init failed: {mt5.last_error()}")
    logging.info("Bot with logging started.")
    for p in PAIRS:
        mt5.symbol_select(p, True)
    while True:
        try:
            cycle_once()
        except Exception as e:
            logging.exception(f"Cycle error: {e}")
        wait = random.randint(MIN_RECHECK*60, MAX_RECHECK*60)
        logging.info(f"Next cycle in {wait//60}m{wait%60}s")
        time.sleep(wait)

if __name__ == "__main__":
    main()
