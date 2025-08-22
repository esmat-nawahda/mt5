#!/usr/bin/env python3
"""
Enhanced MT5 Bot with Progressive Stop Loss Management
- Monitors winning trades every 1 second
- Automatically places SL at €20 profit
- Moves SL up every additional €20 profit increment
- Protects profits progressively as trades become more profitable
"""

import os, time, random, logging, json, uuid, threading
import MetaTrader5 as mt5
import requests, yaml
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
from news_filter import is_blocked_now, next_blocking_event
from trading_logger import init_logger, log_trade, log_analysis_prompt
from colorful_logger import *
from enhanced_config_btc_xau import (
    TRADING_INSTRUMENTS, INSTRUMENTS_CONFIG, NEWS_FILTERING_CONFIG,
    RANGE_DETECTION_CONFIG, TP_SL_ADJUSTMENT_CONFIG, RISK_MANAGEMENT_CONFIG,
    SYSTEM_CONFIG, PROMPT_CONFIG, TRADING_HOURS_CONFIG, get_instrument_config,
    get_tp_sl_adjustment, is_instrument_allowed, validate_config
)

load_dotenv()

# Configuration
PAIRS = TRADING_INSTRUMENTS
LLM_URL = SYSTEM_CONFIG['deepseek_config']['base_url']
if not LLM_URL.endswith('/chat/completions'):
    LLM_URL = LLM_URL.rstrip('/') + '/chat/completions'
LLM_MODEL = SYSTEM_CONFIG['deepseek_config']['model']
LLM_KEY = SYSTEM_CONFIG['deepseek_config']['api_key']
MIN_RECHECK = int(os.getenv("MIN_RECHECK_MINUTES", "1"))
MAX_RECHECK = int(os.getenv("MAX_RECHECK_MINUTES", "2"))
DEVIATION = SYSTEM_CONFIG['mt5_config']['slippage']
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "78"))

MT5_LOGIN = SYSTEM_CONFIG['mt5_config']['login']
MT5_PASSWORD = SYSTEM_CONFIG['mt5_config']['password']
MT5_SERVER = SYSTEM_CONFIG['mt5_config']['server']
MAGIC_NUMBER = SYSTEM_CONFIG['mt5_config']['magic_number']

# Progressive SL Configuration
PROFIT_MONITOR_INTERVAL = 1  # Check winning trades every 1 second
PROFIT_THRESHOLD = 20.0  # €20 profit increments
SIGNAL_CHECK_INTERVAL = 30  # Check for signal changes every 30 seconds

# Global variables
cycle_count = 0
positions_at_breakeven = set()
position_sl_levels = {}  # Track SL levels for each position {ticket: last_sl_level}
precalc_cache = {
    'account_info': None,
    'position_sizes': {},
    'spread_info': {},
    'last_update': 0
}

# Store last known signals for each symbol
last_signals = {}
profit_monitor_thread = None
signal_monitor_thread = None
stop_monitoring = False

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

def calculate_progressive_sl(position, current_profit: float) -> float:
    """Calculate progressive SL based on profit level
    
    Returns the new SL price based on profit increments of €20
    """
    entry_price = position.price_open
    symbol = position.symbol
    
    # Determine how many €20 increments we've reached
    profit_level = int(current_profit // PROFIT_THRESHOLD) * PROFIT_THRESHOLD
    
    if profit_level < PROFIT_THRESHOLD:
        return 0  # No SL until first €20 profit
    
    # Get symbol info for pip calculation
    symbol_info = mt5.symbol_info(symbol)
    if not symbol_info:
        return 0
    
    # Calculate SL offset based on profit level
    # At €20: SL at breakeven
    # At €40: SL at +€10 profit
    # At €60: SL at +€30 profit
    # At €80: SL at +€50 profit
    # Pattern: Lock in (profit_level - 20) / 2 of the profit
    
    locked_profit = max(0, (profit_level - PROFIT_THRESHOLD) / 2)
    
    # Convert locked profit to price distance
    # This is approximate - actual calculation depends on lot size
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return 0
    
    current_price = tick.bid if position.type == mt5.POSITION_TYPE_BUY else tick.ask
    price_movement = abs(current_price - entry_price)
    
    if price_movement == 0:
        return 0
    
    # Calculate what portion of movement to lock in
    profit_per_point = current_profit / price_movement if price_movement > 0 else 0
    points_to_lock = locked_profit / profit_per_point if profit_per_point > 0 else 0
    
    if position.type == mt5.POSITION_TYPE_BUY:
        # For BUY: SL below entry
        if profit_level == PROFIT_THRESHOLD:
            # First €20: SL at breakeven
            new_sl = entry_price
        else:
            # Lock in progressive profit
            new_sl = entry_price + points_to_lock
    else:
        # For SELL: SL above entry
        if profit_level == PROFIT_THRESHOLD:
            # First €20: SL at breakeven
            new_sl = entry_price
        else:
            # Lock in progressive profit
            new_sl = entry_price - points_to_lock
    
    return new_sl

def modify_position_sl(ticket: int, new_sl: float, tp: float, reason: str = "Progressive SL"):
    """Modify position stop loss"""
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": ticket,
        "sl": new_sl,
        "magic": MAGIC_NUMBER,
        "comment": reason
    }
    
    # Only add TP if it exists
    if tp and tp > 0:
        request["tp"] = tp
    
    result = mt5.order_send(request)
    
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        return True
    else:
        error_msg = f"Failed to modify SL: {result.retcode if result else 'Unknown error'}"
        print_error(error_msg)
        return False

def monitor_profit_positions():
    """Monitor winning positions every 1 second for progressive SL management"""
    global position_sl_levels, stop_monitoring
    
    print_info("💰 Starting profit monitoring (1-second intervals)")
    
    while not stop_monitoring:
        try:
            positions = mt5.positions_get()
            
            if positions:
                for position in positions:
                    current_profit = position.profit
                    ticket = position.ticket
                    symbol = position.symbol
                    
                    # Only process winning trades
                    if current_profit >= PROFIT_THRESHOLD:
                        # Determine profit level (€20 increments)
                        profit_level = int(current_profit // PROFIT_THRESHOLD) * PROFIT_THRESHOLD
                        
                        # Check if we need to update SL
                        last_level = position_sl_levels.get(ticket, 0)
                        
                        if profit_level > last_level:
                            # New profit level reached!
                            current_sl = position.sl if position.sl else 0
                            new_sl = calculate_progressive_sl(position, current_profit)
                            
                            # Only modify if new SL is better than current
                            should_modify = False
                            
                            if position.type == mt5.POSITION_TYPE_BUY:
                                # For BUY: new SL should be higher than current
                                should_modify = new_sl > current_sl
                            else:
                                # For SELL: new SL should be lower than current (or current is 0)
                                should_modify = (current_sl == 0) or (new_sl < current_sl)
                            
                            if should_modify and new_sl != 0:
                                print_success(f"💰 PROFIT MILESTONE: {symbol} reached €{profit_level:.0f} profit!")
                                print_info(f"   Current profit: €{current_profit:.2f}")
                                print_info(f"   Moving SL from {current_sl:.5f} to {new_sl:.5f}")
                                
                                # Determine reason message
                                if profit_level == PROFIT_THRESHOLD:
                                    reason = f"SL at breakeven (€{PROFIT_THRESHOLD} profit)"
                                else:
                                    locked = (profit_level - PROFIT_THRESHOLD) / 2
                                    reason = f"Locking €{locked:.0f} profit (€{profit_level} reached)"
                                
                                if modify_position_sl(ticket, new_sl, position.tp if position.tp else 0, reason):
                                    print_success(f"✅ Progressive SL updated - {reason}")
                                    position_sl_levels[ticket] = profit_level
                                    
                                    # Log the modification
                                    log_trade(
                                        str(ticket),
                                        symbol,
                                        "PROGRESSIVE_SL",
                                        0,
                                        "",
                                        new_sl,
                                        position.tp if position.tp else 0,
                                        status="MODIFIED",
                                        reason=reason
                                    )
                    
                    # Clean up closed positions from tracking
                    elif ticket in position_sl_levels and current_profit < 0:
                        # Position turned negative, remove from tracking
                        del position_sl_levels[ticket]
                
                # Clean up tracking for closed positions
                open_tickets = {p.ticket for p in positions}
                closed_tickets = [t for t in position_sl_levels.keys() if t not in open_tickets]
                for ticket in closed_tickets:
                    del position_sl_levels[ticket]
            
        except Exception as e:
            print_error(f"Error in profit monitoring: {e}")
        
        # Check every 1 second
        time.sleep(PROFIT_MONITOR_INTERVAL)

def calculate_technical_indicators(symbol: str):
    """Calculate technical indicators for the prompt"""
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
    
    # Calculate inside lookback
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
        
        if high_break or low_break:
            return "Breakout"
        elif abs(recent['close'].iloc[-1] - recent['close'].iloc[-5]) < atr_h1_points * 0.3:
            return "Pullback"
        else:
            return "None"
    
    m5_setup = detect_setup(df_m5)
    
    # Volume analysis
    if 'real_volume' in df_m5.columns and df_m5['real_volume'].iloc[-1] > 0:
        current_volume = int(df_m5['real_volume'].iloc[-1])
        volume_ma = df_m5['real_volume'].rolling(window=50).mean()
        volume_ok = df_m5['real_volume'].iloc[-1] > volume_ma.iloc[-1] if len(volume_ma) >= 50 else True
    elif 'tick_volume' in df_m5.columns:
        current_volume = int(df_m5['tick_volume'].iloc[-1])
        volume_ma = df_m5['tick_volume'].rolling(window=50).mean()
        volume_ok = df_m5['tick_volume'].iloc[-1] > volume_ma.iloc[-1] if len(volume_ma) >= 50 else True
    else:
        current_volume = 0
        volume_ok = True
    
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
        ny_open_boost = True
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
            "range_low_h1": round(range_low, 5),
            "current_volume": current_volume
        },
        "mtf_state": {
            "H1_trend": h1_trend,
            "M15_trend": m15_trend,
            "M5_setup": m5_setup,
            "volume_ok": volume_ok,
            "obv_agrees": True
        }
    }

def get_ai_signal(symbol: str) -> dict:
    """Get current AI signal for a symbol"""
    try:
        # Calculate technical indicators
        tech_data = calculate_technical_indicators(symbol)
        if not tech_data:
            return {"action": "NO_TRADE", "confidence": 0}
        
        # Get account info
        account = mt5.account_info()
        if not account:
            return {"action": "NO_TRADE", "confidence": 0}
        
        # Check news
        blocked, reason = is_blocked_now(symbol)
        if blocked:
            return {"action": "NO_TRADE", "confidence": 0, "reason": f"News block: {reason}"}
        
        # Get instrument config
        instrument_config = get_instrument_config(symbol)
        instrument_type = instrument_config.get('type', 'unknown')
        
        # Build simplified prompt for signal checking
        prompt = f"""
SYMBOL: {symbol}
PRICE: {tech_data['price']}
H1_TREND: {tech_data['mtf_state']['H1_trend']}
M15_TREND: {tech_data['mtf_state']['M15_trend']}
M5_SETUP: {tech_data['mtf_state']['M5_setup']}
ADX: {tech_data['measures']['adx14_h1']}
ATR%: {tech_data['measures']['atr_h1_pct']}

Analyze and provide trading signal. Min confidence 78%.

RESPOND IN YAML:
action: BUY/SELL/NO_TRADE
confidence: <float 0-100>
entry: <price>
sl: <price>
tp: <price>
"""
        
        headers = {"Authorization": f"Bearer {LLM_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": LLM_MODEL,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": "You are a trading AI. Return YAML only."},
                {"role": "user", "content": prompt}
            ]
        }
        
        r = requests.post(LLM_URL, headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        
        # Parse response
        if content.startswith("```"):
            lines = content.split('\n')
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = '\n'.join(lines)
        
        parsed = yaml.safe_load(content)
        return {
            "action": parsed.get("action", "NO_TRADE"),
            "confidence": float(parsed.get("confidence", 0)),
            "entry": parsed.get("entry"),
            "sl": parsed.get("sl"),
            "tp": parsed.get("tp")
        }
        
    except Exception as e:
        print_error(f"Error getting AI signal for {symbol}: {e}")
        return {"action": "NO_TRADE", "confidence": 0}

def close_position(position):
    """Close a specific position"""
    try:
        symbol = position.symbol
        ticket = position.ticket
        volume = position.volume
        
        # Determine closing order type
        if position.type == mt5.POSITION_TYPE_BUY:
            order_type = mt5.ORDER_TYPE_SELL
        else:
            order_type = mt5.ORDER_TYPE_BUY
        
        close_request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": ticket,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "magic": MAGIC_NUMBER,
            "comment": "Signal reversal - auto close",
            "type_filling": mt5.ORDER_FILLING_IOC
        }
        
        result = mt5.order_send(close_request)
        
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            print_success(f"✅ Closed {symbol} position #{ticket} due to signal change")
            
            # Clean up tracking
            if ticket in position_sl_levels:
                del position_sl_levels[ticket]
            
            log_trade(
                str(ticket),
                symbol,
                "CLOSE",
                0,
                "",
                "",
                "",
                status="AUTO_CLOSED",
                reason="Signal reversal detected"
            )
            return True
        else:
            print_error(f"❌ Failed to close {symbol} position: {result.retcode if result else 'Unknown error'}")
            return False
            
    except Exception as e:
        print_error(f"Error closing position: {e}")
        return False

def monitor_signal_changes():
    """Monitor for signal changes every 30 seconds"""
    global last_signals, stop_monitoring
    
    print_info("🔄 Starting signal monitoring (30-second intervals)")
    
    while not stop_monitoring:
        try:
            positions = mt5.positions_get()
            
            if positions:
                for position in positions:
                    symbol = position.symbol
                    current_type = "BUY" if position.type == mt5.POSITION_TYPE_BUY else "SELL"
                    
                    # Get current AI signal
                    current_signal = get_ai_signal(symbol)
                    last_signals[symbol] = current_signal
                    
                    new_action = current_signal.get("action", "NO_TRADE")
                    confidence = current_signal.get("confidence", 0)
                    
                    # Check for signal reversal
                    if new_action in ["BUY", "SELL"] and confidence >= MIN_CONFIDENCE:
                        if current_type != new_action:
                            print_warning(f"⚠️ SIGNAL REVERSAL: {symbol} {current_type} → {new_action}")
                            print_info(f"    Closing position immediately...")
                            close_position(position)
            
        except Exception as e:
            print_error(f"Error in signal monitoring: {e}")
        
        # Wait 30 seconds before next check
        time.sleep(SIGNAL_CHECK_INTERVAL)

def start_monitoring_threads():
    """Start both monitoring threads"""
    global profit_monitor_thread, signal_monitor_thread, stop_monitoring
    
    stop_monitoring = False
    
    # Start profit monitoring thread (1 second intervals)
    profit_monitor_thread = threading.Thread(target=monitor_profit_positions, daemon=True)
    profit_monitor_thread.start()
    print_success("✅ Started profit monitoring (1-second intervals)")
    
    # Start signal monitoring thread (30 second intervals)
    signal_monitor_thread = threading.Thread(target=monitor_signal_changes, daemon=True)
    signal_monitor_thread.start()
    print_success("✅ Started signal monitoring (30-second intervals)")

def stop_monitoring_threads():
    """Stop all monitoring threads"""
    global stop_monitoring
    
    stop_monitoring = True
    print_info("Stopping monitoring threads...")
    
    if profit_monitor_thread:
        profit_monitor_thread.join(timeout=5)
    if signal_monitor_thread:
        signal_monitor_thread.join(timeout=5)
    
    print_success("Monitoring threads stopped")

def calculate_lot_size(symbol: str, account_equity: float) -> float:
    """Calculate dynamic lot size based on capital"""
    lot_config = RISK_MANAGEMENT_CONFIG['dynamic_lot_sizing']
    
    if not lot_config.get('enabled', True):
        return lot_config.get('base_lot_size', 1.0)
    
    base_lot_size = lot_config.get('base_lot_size', 1.0)
    starting_capital = lot_config.get('starting_capital', 10000.0)
    capital_increment = lot_config.get('capital_increment', 5000.0)
    lot_increment = lot_config.get('lot_increment', 0.5)
    min_lot_size = lot_config.get('min_lot_size', 1.0)
    
    capital_change = account_equity - starting_capital
    additional_lots = (capital_change / capital_increment) * lot_increment
    final_lot_size = base_lot_size + additional_lots
    final_lot_size = max(min_lot_size, final_lot_size)
    
    return round(final_lot_size, 1)

def open_trade(symbol: str, action: str, sl: float, tp: float):
    """Open a new trade"""
    try:
        ensure_symbol(symbol)
        tick = mt5.symbol_info_tick(symbol)
        account = mt5.account_info()
        
        if action.upper() == "BUY":
            price = tick.ask
            otype = mt5.ORDER_TYPE_BUY
        elif action.upper() == "SELL":
            price = tick.bid
            otype = mt5.ORDER_TYPE_SELL
        else:
            return None
        
        volume = calculate_lot_size(symbol, account.equity)
        
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": otype,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": DEVIATION,
            "magic": MAGIC_NUMBER,
            "comment": "AI Signal",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        print_info(f"Opening {action} {symbol} @ {price:.5f}")
        print_info(f"  Volume: {volume} | SL: {sl:.5f} | TP: {tp:.5f}")
        
        res = mt5.order_send(req)
        
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            print_success(f"✅ Order executed! Ticket: {res.order}")
            
            # Store initial signal
            last_signals[symbol] = {"action": action, "confidence": 100}
            
            return res
        else:
            print_error(f"Order failed: {res.retcode if res else 'Unknown error'}")
            return None
            
    except Exception as e:
        print_error(f"Error opening trade: {e}")
        return None

def display_profit_status():
    """Display current profit protection status"""
    positions = mt5.positions_get()
    if positions:
        print_separator()
        print_info("💰 PROFIT PROTECTION STATUS")
        for position in positions:
            profit = position.profit
            symbol = position.symbol
            ticket = position.ticket
            
            if profit > 0:
                profit_level = int(profit // PROFIT_THRESHOLD) * PROFIT_THRESHOLD
                next_level = profit_level + PROFIT_THRESHOLD
                
                status = ""
                if ticket in position_sl_levels:
                    locked_level = position_sl_levels[ticket]
                    if locked_level >= PROFIT_THRESHOLD:
                        locked_profit = max(0, (locked_level - PROFIT_THRESHOLD) / 2)
                        status = f" [Protected: €{locked_profit:.0f}]"
                
                print_info(f"  {symbol}: €{profit:.2f} profit{status}")
                
                if profit < next_level:
                    remaining = next_level - profit
                    print_info(f"    → €{remaining:.2f} to next SL level (€{next_level})")
                else:
                    print_success(f"    → Ready for SL adjustment!")

def main():
    """Main function with progressive SL monitoring"""
    # Validate configuration
    if not validate_config():
        print_error("Configuration validation failed")
        return
    
    init_logger()
    print_header()
    print_info("MT5 Bot with Progressive Stop Loss Management")
    print_info(f"Trading instruments: {', '.join(TRADING_INSTRUMENTS)}")
    print_info(f"Profit check interval: {PROFIT_MONITOR_INTERVAL} second")
    print_info(f"SL placement: Every €{PROFIT_THRESHOLD} profit")
    print_info("SL Strategy:")
    print_info("  €20 profit → SL at breakeven")
    print_info("  €40 profit → SL locks €10")
    print_info("  €60 profit → SL locks €30")
    print_info("  €80 profit → SL locks €50")
    
    # Initialize MT5
    try:
        if not mt5.initialize():
            if not mt5.initialize(login=MT5_LOGIN or None, password=MT5_PASSWORD or None, server=MT5_SERVER or None):
                raise RuntimeError(f"MT5 init failed: {mt5.last_error()}")
        
        account = mt5_init()
    except Exception as e:
        print_error(f"Failed to connect to MT5: {e}")
        return
    
    # Select symbols
    for p in PAIRS:
        try:
            mt5.symbol_select(p, True)
            print(f"  {Colors.GREEN}[OK]{Colors.RESET} {p} selected")
        except Exception as e:
            print(f"  {Colors.RED}[X]{Colors.RESET} {p} failed: {e}")
    
    # Start monitoring threads
    start_monitoring_threads()
    
    print_success("Bot initialized with progressive SL protection!")
    print_warning("Winning trades monitored every 1 second")
    print_warning("Positions auto-close on signal reversal")
    
    # Main loop for opening new positions
    while True:
        try:
            # Display profit status
            display_profit_status()
            
            # Check for new trading opportunities
            positions = mt5.positions_get()
            open_symbols = [p.symbol for p in positions] if positions else []
            
            for symbol in PAIRS:
                if symbol not in open_symbols:
                    # No position for this symbol, check for entry
                    signal = get_ai_signal(symbol)
                    
                    if signal["action"] in ["BUY", "SELL"] and signal["confidence"] >= MIN_CONFIDENCE:
                        print_info(f"New signal for {symbol}: {signal['action']} (Confidence: {signal['confidence']:.1f}%)")
                        
                        if signal.get("entry") and signal.get("sl") and signal.get("tp"):
                            open_trade(symbol, signal["action"], signal["sl"], signal["tp"])
            
        except Exception as e:
            print_error(f"Error in main loop: {e}")
        
        # Wait before next cycle
        wait = random.randint(MIN_RECHECK*60, MAX_RECHECK*60)
        print_info(f"Next opportunity check in {wait//60} minutes...")
        time.sleep(wait)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_warning("\nStopping bot...")
        stop_monitoring_threads()
        mt5.shutdown()
        print_success("Bot stopped")
    except Exception as e:
        print_error(f"Fatal error: {e}")
        stop_monitoring_threads()
        mt5.shutdown()