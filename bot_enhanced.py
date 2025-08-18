#!/usr/bin/env python3
"""
Enhanced MT5 Multi-Pair Autotrader with Colorful Logging
Using Thanatos-Guardian-Prime v15.2-MAXPROTECT prompt
- Pairs: XAUUSD, BTCUSD (configurable)
- Random re-check 3–5 minutes
- Prioritize most confident pair from DeepSeek
- Block trading 60 min before/after high-impact news
- Enhanced colorful console output with detailed analysis
"""

import os, time, random, logging, json, uuid
import MetaTrader5 as mt5
import requests, yaml
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv
from news_filter import is_blocked_now, next_blocking_event
from trading_logger import init_logger, log_trade, log_analysis_prompt
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

def calculate_technical_indicators(symbol: str):
    """Calculate technical indicators for the prompt"""
    # Get H1 data for indicators
    rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)
    rates_m15 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 100)
    rates_m5 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 100)
    
    if rates_h1 is None or len(rates_h1) < 30:
        return None
    
    df_h1 = pd.DataFrame(rates_h1)
    df_m15 = pd.DataFrame(rates_m15)
    df_m5 = pd.DataFrame(rates_m5)
    
    current_price = float(df_h1['close'].iloc[-1])
    
    # Calculate ADX(14) on H1
    def calculate_adx(df, period=14):
        high = df['high']
        low = df['low']
        close = df['close']
        
        plus_dm = high.diff()
        minus_dm = low.diff().abs()
        tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
        
        atr = tr.rolling(window=period).mean()
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        
        return adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 20.0
    
    adx14_h1 = calculate_adx(df_h1)
    
    # Calculate ATR(14) on H1
    high = df_h1['high']
    low = df_h1['low']
    close = df_h1['close']
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr_h1_points = tr.rolling(window=14).mean().iloc[-1]
    atr_h1_pct = (atr_h1_points / current_price) * 100
    
    # Calculate Bollinger Bands width
    sma20 = df_h1['close'].rolling(window=20).mean()
    std20 = df_h1['close'].rolling(window=20).std()
    bb_upper = sma20 + (2 * std20)
    bb_lower = sma20 - (2 * std20)
    bb20_width_pct_h1 = ((bb_upper.iloc[-1] - bb_lower.iloc[-1]) / current_price) * 100
    
    # Calculate inside lookback (consolidation detection)
    recent_range = df_h1.tail(15)
    range_high = recent_range['high'].max()
    range_low = recent_range['low'].min()
    inside_lookback_h1 = 0
    for i in range(1, 16):
        if df_h1['high'].iloc[-i] <= range_high and df_h1['low'].iloc[-i] >= range_low:
            inside_lookback_h1 += 1
    
    # Determine trends
    def determine_trend(df):
        sma50 = df['close'].rolling(window=50).mean()
        sma20 = df['close'].rolling(window=20).mean()
        if len(sma50) < 50:
            return "Sideways"
        
        current = df['close'].iloc[-1]
        if current > sma20.iloc[-1] and sma20.iloc[-1] > sma50.iloc[-1]:
            return "Bullish"
        elif current < sma20.iloc[-1] and sma20.iloc[-1] < sma50.iloc[-1]:
            return "Bearish"
        else:
            return "Sideways"
    
    h1_trend = determine_trend(df_h1)
    m15_trend = determine_trend(df_m15) if len(df_m15) >= 50 else "Sideways"
    
    # Detect M5 setup
    def detect_setup(df):
        if len(df) < 20:
            return "None"
        
        recent = df.tail(10)
        high_break = recent['close'].iloc[-1] > recent['high'].iloc[:-1].max()
        low_break = recent['close'].iloc[-1] < recent['low'].iloc[:-1].min()
        
        if high_break:
            return "Breakout"
        elif low_break:
            return "Breakout"
        elif abs(recent['close'].iloc[-1] - recent['close'].iloc[-5]) < atr_h1_points * 0.3:
            return "Pullback"
        else:
            return "None"
    
    m5_setup = detect_setup(df_m5)
    
    # Volume analysis
    volume_ma = df_m5['real_volume'].rolling(window=50).mean()
    volume_ok = df_m5['real_volume'].iloc[-1] > volume_ma.iloc[-1] if len(volume_ma) >= 50 else True
    
    # Get current session
    now = datetime.now()
    hour = now.hour
    if 8 <= hour < 12:
        active_session = "London"
        ny_open_boost = False
    elif 14 <= hour < 17:
        active_session = "New York"
        ny_open_boost = True
    elif 12 <= hour < 14:
        active_session = "London"
        ny_open_boost = True  # Overlap
    else:
        active_session = "Asian"
        ny_open_boost = False
    
    return {
        "timestamp_cet": now.strftime("%Y-%m-%d %H:%M"),
        "price": current_price,
        "sessions": {"active": active_session, "ny_open_boost": ny_open_boost},
        "measures": {
            "adx14_h1": round(adx14_h1, 1),
            "atr_h1_points": round(atr_h1_points, 2),
            "atr_h1_pct": round(atr_h1_pct, 2),
            "bb20_width_pct_h1": round(bb20_width_pct_h1, 2),
            "inside_lookback_h1": inside_lookback_h1,
            "range_high_h1": round(range_high, 5),
            "range_low_h1": round(range_low, 5)
        },
        "mtf_state": {
            "H1_trend": h1_trend,
            "M15_trend": m15_trend,
            "M5_setup": m5_setup,
            "volume_ok": volume_ok,
            "obv_agrees": True  # Simplified
        }
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
        "comment": "Thanatos AI Bot",
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

def deepseek_analyze(symbol: str, technical_data: dict, account_info) -> dict:
    """Use the Thanatos-Guardian-Prime prompt"""
    headers = {"Authorization": f"Bearer {LLM_KEY}", "Content-Type":"application/json"}
    
    # Check news
    blocked, reason = is_blocked_now(symbol)
    red_news_window = blocked
    
    # Check UK close
    now = datetime.now()
    uk_close_block = now.hour >= 16 and now.minute >= 30
    
    # Get spread
    tick = mt5.symbol_info_tick(symbol)
    spread = tick.ask - tick.bid if tick else 0
    spread_ok = spread < 0.0010 if symbol == "EURUSD" else spread < 10 if "XAU" in symbol else True
    
    # Build the prompt with the exact template
    prompt = f"""You are a trading AI following the Thanatos-Guardian-Prime v15.2-MAXPROTECT protocol.
Analyze this market data and return STRICT YAML response.

meta:
  version: "15.2-MAXPROTECT"
  codename: "Thanatos-Guardian-Prime"
  response_rules: "STRICT_YAML_ONLY | TRIPLE_PASS_REQUIRED"
  min_confidence_threshold: "78%"

inputs:
  symbol: "{symbol}"
  timestamp_cet: "{technical_data['timestamp_cet']}"
  price: {technical_data['price']}
  sessions: {{active: "{technical_data['sessions']['active']}", ny_open_boost: {str(technical_data['sessions']['ny_open_boost']).lower()}}}
  measures:
    adx14_h1: {technical_data['measures']['adx14_h1']}
    atr_h1_points: {technical_data['measures']['atr_h1_points']}
    atr_h1_pct: {technical_data['measures']['atr_h1_pct']}
    bb20_width_pct_h1: {technical_data['measures']['bb20_width_pct_h1']}
    inside_lookback_h1: {technical_data['measures']['inside_lookback_h1']}
    range_high_h1: {technical_data['measures']['range_high_h1']}
    range_low_h1: {technical_data['measures']['range_low_h1']}
  mtf_state:
    H1_trend: "{technical_data['mtf_state']['H1_trend']}"
    M15_trend: "{technical_data['mtf_state']['M15_trend']}"
    M5_setup: "{technical_data['mtf_state']['M5_setup']}"
    volume_ok: {str(technical_data['mtf_state']['volume_ok']).lower()}
    obv_agrees: {str(technical_data['mtf_state']['obv_agrees']).lower()}
  risk_context:
    active_trades: {len(open_positions_map())}
    equity_usd: {account_info.equity}
    red_news_window: {str(red_news_window).lower()}
    uk_close_block: {str(uk_close_block).lower()}
    spread_ok: {str(spread_ok).lower()}
    slippage_guard_ok: true

Based on all filters and the anti-range rules, provide a trading decision.
Return ONLY this YAML structure:

action: "BUY" or "SELL" or "NO_TRADE"
confidence: <float 0-100>
entry: <float if BUY/SELL>
sl: <float if BUY/SELL>
tp1: <float if BUY/SELL>
tp2: <float if BUY/SELL>
tp3: <float if BUY/SELL>
analysis: <string explaining decision>
guardian_status:
  anti_range_pass: <true/false>
  confluence_pass: <true/false>
  max_protect_pass: <true/false>

Apply all rules:
- ADX > 20 required for trend
- ATR% >= 0.35% required for volatility
- BB width >= 0.6% required
- No trade if last 15 H1 candles in consolidation
- No trade during news or after UK close
- No trade if active_trades >= 2
- Minimum 78% confidence required
"""
    
    payload = {
        "model": LLM_MODEL,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": "You are Thanatos-Guardian-Prime trading AI. Follow all protocol rules strictly. Return ONLY valid YAML."},
            {"role": "user", "content": prompt}
        ]
    }
    
    # Extract all checked rules for logging
    checked_rules = {
        "ADX_threshold": {"value": technical_data['measures']['adx14_h1'], "required": 20, "passed": technical_data['measures']['adx14_h1'] > 20},
        "ATR_threshold": {"value": technical_data['measures']['atr_h1_pct'], "required": 0.35, "passed": technical_data['measures']['atr_h1_pct'] >= 0.35},
        "BB_width_threshold": {"value": technical_data['measures']['bb20_width_pct_h1'], "required": 0.6, "passed": technical_data['measures']['bb20_width_pct_h1'] >= 0.6},
        "consolidation_check": {"inside_bars": technical_data['measures']['inside_lookback_h1'], "max_allowed": 15, "passed": technical_data['measures']['inside_lookback_h1'] < 15},
        "news_filter": {"blocked": red_news_window, "reason": reason if red_news_window else "Clear"},
        "uk_close_filter": {"blocked": uk_close_block, "time": f"{now.hour}:{now.minute:02d}"},
        "active_trades": {"count": len(open_positions_map()), "max_allowed": 2, "passed": len(open_positions_map()) < 2},
        "spread_check": {"ok": spread_ok, "spread": spread},
        "session": technical_data['sessions']['active'],
        "ny_open_boost": technical_data['sessions']['ny_open_boost'],
        "H1_trend": technical_data['mtf_state']['H1_trend'],
        "M15_trend": technical_data['mtf_state']['M15_trend'],
        "M5_setup": technical_data['mtf_state']['M5_setup'],
        "volume_ok": technical_data['mtf_state']['volume_ok'],
        "min_confidence_required": MIN_CONFIDENCE
    }
    
    print_info("Requesting Thanatos-Guardian-Prime analysis...")
    r = requests.post(LLM_URL, headers=headers, json=payload, timeout=30)
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
        
        # Log the prompt and analysis
        log_analysis_prompt(symbol, prompt, checked_rules, parsed)
        
        return parsed
    except Exception as e:
        print_error(f"Failed to parse AI response: {e}")
        # Return safe NO_TRADE response
        safe_response = {
            "action": "NO_TRADE",
            "confidence": 0.0,
            "analysis": "Failed to parse AI response",
            "guardian_status": {
                "anti_range_pass": False,
                "confluence_pass": False,
                "max_protect_pass": False
            }
        }
        
        # Log even failed parsing attempts
        log_analysis_prompt(symbol, prompt, checked_rules, {"error": str(e), "raw_content": content})
        
        return safe_response

def cycle_once():
    global cycle_count
    cycle_count += 1
    
    print_cycle_start(cycle_count)
    
    # Get account info
    account = mt5.account_info()
    if not account:
        print_error("Failed to get account info")
        return
    
    # Get current positions
    open_pos = open_positions_map()
    print_position_status(open_pos)
    
    # Check if we have max trades
    if len(open_pos) >= 2:
        print_warning("Maximum trades (2) already open. Skipping analysis.")
        return
    
    # Check news
    print_separator()
    blocked_pairs = {}
    for symbol in PAIRS:
        blocked, reason = is_blocked_now(symbol)
        if blocked:
            blocked_pairs[symbol] = reason
    print_news_status(blocked_pairs)
    
    # Analyze each pair
    print_separator()
    signals = []
    
    for symbol in PAIRS:
        print_info(f"Analyzing {symbol}...")
        
        try:
            # Calculate technical indicators
            tech_data = calculate_technical_indicators(symbol)
            if not tech_data:
                print_error(f"Failed to calculate indicators for {symbol}")
                continue
            
            # Display market data
            print_market_data(symbol, tech_data['price'], {
                "high": tech_data['measures']['range_high_h1'],
                "low": tech_data['measures']['range_low_h1'],
                "volume": 0  # Simplified
            })
            
            # Display technical indicators
            print(f"  {Colors.WHITE}ADX(14): {Colors.CYAN}{tech_data['measures']['adx14_h1']}{Colors.RESET}")
            print(f"  {Colors.WHITE}ATR%: {Colors.CYAN}{tech_data['measures']['atr_h1_pct']:.2f}%{Colors.RESET}")
            print(f"  {Colors.WHITE}BB Width%: {Colors.CYAN}{tech_data['measures']['bb20_width_pct_h1']:.2f}%{Colors.RESET}")
            print(f"  {Colors.WHITE}H1 Trend: {Colors.CYAN}{tech_data['mtf_state']['H1_trend']}{Colors.RESET}")
            print(f"  {Colors.WHITE}Session: {Colors.CYAN}{tech_data['sessions']['active']}{Colors.RESET}")
            
            # Get AI analysis
            analysis = deepseek_analyze(symbol, tech_data, account)
            
            # Add to signals list
            signals.append({
                "symbol": symbol,
                "action": analysis.get("action", "NO_TRADE"),
                "confidence": float(analysis.get("confidence", 0)),
                "entry": analysis.get("entry"),
                "sl": analysis.get("sl"),
                "tp": analysis.get("tp1"),  # Use first TP
                "tp2": analysis.get("tp2"),
                "tp3": analysis.get("tp3"),
                "analysis": analysis.get("analysis", ""),
                "guardian": analysis.get("guardian_status", {})
            })
            
        except Exception as e:
            print_error(f"Error analyzing {symbol}: {e}")
            continue
    
    # Process signals (highest confidence first)
    signals = sorted(signals, key=lambda x: x["confidence"], reverse=True)
    
    for sig in signals:
        symbol = sig["symbol"]
        action = sig["action"].upper()
        confidence = sig["confidence"]
        
        # Display AI analysis
        print_ai_analysis(
            symbol, action, confidence,
            sig.get("entry"), sig.get("sl"), sig.get("tp")
        )
        
        if sig.get("analysis"):
            print(f"  {Colors.DIM}Analysis: {sig['analysis']}{Colors.RESET}")
        
        # Display guardian status
        guardian = sig.get("guardian", {})
        if guardian:
            status_color = Colors.GREEN if all([
                guardian.get("anti_range_pass", False),
                guardian.get("confluence_pass", False),
                guardian.get("max_protect_pass", False)
            ]) else Colors.RED
            print(f"  {Colors.WHITE}Guardian Filters:{Colors.RESET}")
            print(f"    Anti-Range: {status_color}{'PASS' if guardian.get('anti_range_pass') else 'FAIL'}{Colors.RESET}")
            print(f"    Confluence: {status_color}{'PASS' if guardian.get('confluence_pass') else 'FAIL'}{Colors.RESET}")
            print(f"    MaxProtect: {status_color}{'PASS' if guardian.get('max_protect_pass') else 'FAIL'}{Colors.RESET}")
        
        # Decision logic
        decision_id = str(uuid.uuid4())[:8]
        
        # Check confidence threshold
        if confidence < MIN_CONFIDENCE or action == "NO_TRADE":
            reason = f"Below threshold (min: {MIN_CONFIDENCE}%) or NO_TRADE signal"
            print_trade_decision(symbol, "SKIP", reason)
            log_trade(decision_id, symbol, action, confidence, "", "", "", status="SKIPPED", reason=reason)
            continue
        
        # Check news block
        if symbol in blocked_pairs:
            print_trade_decision(symbol, "BLOCKED", blocked_pairs[symbol])
            log_trade(decision_id, symbol, action, confidence, "", "", "", status="BLOCKED", reason=blocked_pairs[symbol])
            continue
        
        # Check if position already open
        if symbol in open_pos:
            print_trade_decision(symbol, "SKIP", "Position already open")
            log_trade(decision_id, symbol, action, confidence, "", "", "", status="SKIPPED", reason="Already open")
            continue
        
        # Open new position
        entry = sig.get("entry")
        sl = sig.get("sl")
        tp = sig.get("tp")
        
        if entry and sl and tp:
            print_trade_decision(symbol, "OPEN", f"High confidence signal ({confidence:.1f}%) - Thanatos approved")
            res = open_trade(symbol, action, float(sl), float(tp))
            
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                trade_id = str(res.order or res.deal or decision_id)
                log_trade(trade_id, symbol, action, confidence, entry, sl, tp, status="OPEN", reason="Thanatos-Guardian approved")
            else:
                error_msg = f"Order failed: {getattr(res,'retcode',None)}"
                print_error(error_msg)
                log_trade(decision_id, symbol, action, confidence, entry, sl, tp, status="ERROR", reason=error_msg)
            break  # Only one new position per cycle
        else:
            print_warning(f"Invalid entry/SL/TP values for {symbol}")

def main():
    init_logger()
    print_header()
    print_info("Using Thanatos-Guardian-Prime v15.2-MAXPROTECT Protocol")
    
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
    
    print_success("Bot initialized with Thanatos-Guardian-Prime!")
    print_info(f"Trading pairs: {', '.join(PAIRS)}")
    print_info(f"Volume per trade: {VOLUME} lots")
    print_info(f"Minimum confidence: {MIN_CONFIDENCE}%")
    print_info(f"Check interval: {MIN_RECHECK}-{MAX_RECHECK} minutes")
    print_warning("Guardian Filters Active: Anti-Range, MaxProtect, News Filter")
    
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