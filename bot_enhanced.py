#!/usr/bin/env python3
"""
Enhanced MT5 Multi-Pair Autotrader with Colorful Logging
- Pairs: XAUUSD, BTCUSD (configurable)
- Random re-check 3–5 minutes
- Prioritize most confident pair from DeepSeek
- Block trading 60 min before/after high-impact news
- Enhanced colorful console output with detailed analysis
"""

import os, time, random, logging, json, uuid
import MetaTrader5 as mt5
import requests, yaml
from dotenv import load_dotenv
from news_filter import is_blocked_now, next_blocking_event
from trading_logger import init_logger, log_trade
from colorful_logger import *

load_dotenv()

# Suppress default logging for cleaner output
logging.basicConfig(level=logging.ERROR)

PAIRS = os.getenv("PAIRS", "XAUUSD,BTCUSD").split(",")
LLM_URL = os.getenv("LLM_URL")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")
LLM_KEY = os.getenv("LLM_API_KEY")
MIN_RECHECK = int(os.getenv("MIN_RECHECK_MINUTES", "3"))
MAX_RECHECK = int(os.getenv("MAX_RECHECK_MINUTES", "5"))
VOLUME = float(os.getenv("VOLUME", "1.00"))
DEVIATION = int(os.getenv("DEVIATION", "30"))
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "78"))

MT5_LOGIN = int(os.getenv("MT5_LOGIN", "0"))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")

cycle_count = 0

def mt5_init():
    if not mt5.initialize(login=MT5_LOGIN or None, password=MT5_PASSWORD or None, server=MT5_SERVER or None):
        raise RuntimeError(f"MT5 init failed: {mt5.last_error()}")
    ai = mt5.account_info()
    if not ai: raise RuntimeError("MT5 account_info failed")
    print_success(f"Connected to MT5 | Account: {ai.login} | Server: {ai.server}")
    print_info(f"Balance: ${ai.balance:.2f} | Equity: ${ai.equity:.2f} | Margin: ${ai.margin:.2f}")
    return ai

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
    recent_high = max(r['high'] for r in rates[-20:])
    recent_low = min(r['low'] for r in rates[-20:])
    
    return {
        "symbol": symbol,
        "last_price": float(last["close"]),
        "high": float(last["high"]),
        "low": float(last["low"]),
        "volume": float(last["real_volume"]),
        "recent_high": recent_high,
        "recent_low": recent_low
    }

def open_positions_map() -> dict:
    positions = mt5.positions_get()
    if positions is None: return {}
    return {p.symbol: p for p in positions}

def open_trade(symbol: str, action: str, sl: float, tp: float):
    ensure_symbol(symbol)
    tick = mt5.symbol_info_tick(symbol)
    if action.upper() == "BUY":
        price = tick.ask
        otype = mt5.ORDER_TYPE_BUY
    elif action.upper() == "SELL":
        price = tick.bid
        otype = mt5.ORDER_TYPE_SELL
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
        "comment": "DeepSeek AI Bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    print_info(f"Sending order: {action} {symbol} @ {price:.5f}")
    res = mt5.order_send(req)
    
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        print_success(f"Order executed! Ticket: {res.order}")
    else:
        print_error(f"Order failed: {res.retcode if res else 'Unknown error'}")
    
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
    
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        print_success(f"Updated SL/TP for {position.symbol}")
    else:
        print_error(f"Failed to update SL/TP: {res.retcode if res else 'Unknown'}")
    
    return res

def deepseek_analyze(market_snapshots: dict) -> dict:
    headers = {"Authorization": f"Bearer {LLM_KEY}", "Content-Type":"application/json"}
    
    # Enhanced prompt with technical analysis request
    user_prompt = f"""
Analyze these forex/crypto pairs and provide trading signals.
Consider price action, support/resistance, and market momentum.

Return STRICT YAML with this exact schema:
pairs:
  - symbol: "XAUUSD" or "BTCUSD"
    action: "BUY" or "SELL" or "NO TRADE"
    confidence: <float 0-100>
    entry: <float, required if BUY/SELL>
    sl: <float, required if BUY/SELL>
    tp: <float, required if BUY/SELL>
    analysis: <brief reason for signal>

Market data (M15 timeframe):
{json.dumps(market_snapshots, indent=2)}

Requirements:
- Only suggest trades with clear setups
- Risk/Reward ratio should be at least 1:1.5
- Set realistic SL and TP based on recent price action
- Confidence reflects signal strength (0-100)
"""
    
    payload = {
        "model": LLM_MODEL,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": "You are an expert forex/crypto trading AI. Analyze markets and provide clear trading signals with proper risk management."},
            {"role": "user", "content": user_prompt}
        ]
    }
    
    print_info("Requesting AI analysis from DeepSeek...")
    r = requests.post(LLM_URL, headers=headers, json=payload, timeout=20)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    
    # Strip markdown code blocks if present
    if content.startswith("```"):
        lines = content.split('\n')
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = '\n'.join(lines)
    
    try:
        parsed = yaml.safe_load(content)
        return parsed
    except Exception as e:
        print_error(f"Failed to parse AI response: {e}")
        raise ValueError(f"DeepSeek returned invalid YAML:\n{content}") from e

def validate_pairs_block(sig: dict):
    required = set(p.strip().upper() for p in PAIRS)
    got = set(p.get("symbol","").upper() for p in sig.get("pairs", []))
    missing = required - got
    if missing:
        raise ValueError(f"Missing pairs in AI response: {missing}")

def check_news_for_all_pairs():
    """Check news status for all trading pairs"""
    blocked_pairs = {}
    for symbol in PAIRS:
        blocked, reason = is_blocked_now(symbol)
        if blocked:
            blocked_pairs[symbol] = reason
    return blocked_pairs

def cycle_once():
    global cycle_count
    cycle_count += 1
    
    print_cycle_start(cycle_count)
    
    # Get current positions
    open_pos = open_positions_map()
    print_position_status(open_pos)
    
    # Check news
    print_separator()
    blocked_pairs = check_news_for_all_pairs()
    print_news_status(blocked_pairs)
    
    # Fetch market data
    print_separator()
    print_info("Fetching market data...")
    snapshots = {}
    for p in PAIRS:
        try:
            snapshot = fetch_snapshot(p)
            snapshots[p] = snapshot
            print_market_data(p, snapshot["last_price"], {
                "high": snapshot["high"],
                "low": snapshot["low"],
                "volume": snapshot["volume"]
            })
        except Exception as e:
            print_error(f"Failed to fetch {p}: {e}")
            return
    
    # Get AI analysis
    print_separator()
    try:
        sig = deepseek_analyze(snapshots)
        validate_pairs_block(sig)
    except Exception as e:
        print_error(f"AI analysis failed: {e}")
        return
    
    # Process signals
    ranked = sorted(sig["pairs"], key=lambda x: x.get("confidence", 0), reverse=True)
    
    for s in ranked:
        sym = s.get("symbol", "").upper()
        action = (s.get("action") or "NO TRADE").upper()
        conf = float(s.get("confidence", 0))
        analysis = s.get("analysis", "")
        
        # Display AI analysis
        print_ai_analysis(
            sym, action, conf,
            s.get("entry"), s.get("sl"), s.get("tp")
        )
        
        if analysis:
            print(f"  {Colors.DIM}Analysis: {analysis}{Colors.RESET}")
        
        # Decision logic
        decision_id = str(uuid.uuid4())[:8]
        
        # Check confidence threshold
        if conf < MIN_CONFIDENCE or action == "NO TRADE":
            reason = f"Below threshold (min: {MIN_CONFIDENCE}%) or NO_TRADE signal"
            print_trade_decision(sym, "SKIP", reason)
            log_trade(decision_id, sym, action, conf, "", "", "", status="SKIPPED", reason=reason)
            continue
        
        # Check news block
        if sym in blocked_pairs:
            print_trade_decision(sym, "BLOCKED", blocked_pairs[sym])
            log_trade(decision_id, sym, action, conf, "", "", "", status="BLOCKED", reason=blocked_pairs[sym])
            continue
        
        # Check if position already open
        if sym in open_pos:
            pos = open_pos[sym]
            if "sl" in s and "tp" in s and s["sl"] and s["tp"]:
                print_trade_decision(sym, "UPDATE", "Adjusting SL/TP for existing position")
                update_sl_tp(pos, float(s["sl"]), float(s["tp"]))
                log_trade(decision_id, sym, action, conf, "", s["sl"], s["tp"], status="UPDATED", reason="Updated SL/TP")
            else:
                print_trade_decision(sym, "SKIP", "Position already open")
                log_trade(decision_id, sym, action, conf, "", "", "", status="SKIPPED", reason="Already open")
            continue
        
        # Open new position
        entry = float(s.get("entry", 0))
        sl = float(s.get("sl", 0))
        tp = float(s.get("tp", 0))
        
        if entry and sl and tp:
            print_trade_decision(sym, "OPEN", f"High confidence signal ({conf:.1f}%)")
            res = open_trade(sym, action, sl, tp)
            
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                trade_id = str(res.order or res.deal or decision_id)
                log_trade(trade_id, sym, action, conf, entry, sl, tp, status="OPEN", reason="Order executed")
            else:
                error_msg = f"Order failed: {getattr(res,'retcode',None)}"
                print_error(error_msg)
                log_trade(decision_id, sym, action, conf, entry, sl, tp, status="ERROR", reason=error_msg)
            break  # Only one new position per cycle
        else:
            print_warning(f"Invalid entry/SL/TP values for {sym}")

def main():
    init_logger()
    print_header()
    
    # Initialize MT5
    try:
        # Try connecting without credentials first (use already logged-in terminal)
        if not mt5.initialize():
            # If that fails, try with credentials
            if not mt5.initialize(login=MT5_LOGIN or None, password=MT5_PASSWORD or None, server=MT5_SERVER or None):
                raise RuntimeError(f"MT5 init failed: {mt5.last_error()}")
        
        account = mt5_init()
    except Exception as e:
        print_error(f"Failed to connect to MT5: {e}")
        return
    
    print_info("Selecting trading symbols...")
    for p in PAIRS:
        try:
            mt5.symbol_select(p, True)
            print(f"  {Colors.GREEN}[OK]{Colors.RESET} {p} selected")
        except Exception as e:
            print(f"  {Colors.RED}[X]{Colors.RESET} {p} failed: {e}")
    
    print_success("Bot initialized and ready to trade!")
    print_info(f"Trading pairs: {', '.join(PAIRS)}")
    print_info(f"Volume per trade: {VOLUME} lots")
    print_info(f"Minimum confidence: {MIN_CONFIDENCE}%")
    print_info(f"Check interval: {MIN_RECHECK}-{MAX_RECHECK} minutes")
    
    # Main trading loop
    while True:
        try:
            cycle_once()
        except Exception as e:
            print_error(f"Cycle error: {e}")
            import traceback
            traceback.print_exc()
        
        # Random wait between cycles
        wait = random.randint(MIN_RECHECK*60, MAX_RECHECK*60)
        print_next_cycle(wait)
        time.sleep(wait)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_warning("\nBot stopped by user")
        mt5.shutdown()
    except Exception as e:
        print_error(f"Fatal error: {e}")
        mt5.shutdown()