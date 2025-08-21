#!/usr/bin/env python3
"""
Enhanced MT5 Multi-Pair Autotrader with Colorful Logging
Using Thanatos-Guardian-Prime v15.2-MAXPROTECT prompt
- Pairs: XAUUSD, BTCUSD (configurable)
- Random re-check 1–2 minutes
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

# Suppress default logging for cleaner output
logging.basicConfig(level=logging.ERROR)

# Use configuration from enhanced_config_btc_xau.py
PAIRS = TRADING_INSTRUMENTS
# Ensure we have the correct endpoint for chat completions
LLM_URL = SYSTEM_CONFIG['deepseek_config']['base_url']
if not LLM_URL.endswith('/chat/completions'):
    LLM_URL = LLM_URL.rstrip('/') + '/chat/completions'
LLM_MODEL = SYSTEM_CONFIG['deepseek_config']['model']
LLM_KEY = SYSTEM_CONFIG['deepseek_config']['api_key']
MIN_RECHECK = int(os.getenv("MIN_RECHECK_MINUTES", "1"))
MAX_RECHECK = int(os.getenv("MAX_RECHECK_MINUTES", "2"))
DEVIATION = SYSTEM_CONFIG['mt5_config']['slippage']
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "70"))

MT5_LOGIN = SYSTEM_CONFIG['mt5_config']['login']
MT5_PASSWORD = SYSTEM_CONFIG['mt5_config']['password']
MT5_SERVER = SYSTEM_CONFIG['mt5_config']['server']
MAGIC_NUMBER = SYSTEM_CONFIG['mt5_config']['magic_number']

# ================================================================
# Trading Hours Check Function
# ================================================================

def is_trading_hours_allowed():
    """Check if current time is within allowed trading hours
    
    Trading windows:
    - Morning: 08:00-12:00 CET
    - Afternoon/Night: 13:00-03:00 CET (next day)
    
    Returns:
        tuple: (bool: allowed, str: reason)
    """
    config = TRADING_HOURS_CONFIG
    
    # Check if trading hours restriction is enabled
    if not config.get('enabled', False):
        return True, "Trading hours check disabled"
    
    # Get current time in CET
    try:
        cet_tz = pytz.timezone('CET')
        current_time = datetime.now(cet_tz)
    except:
        # Fallback to system time if timezone fails
        current_time = datetime.now()
        cet_tz = None
    
    current_day = current_time.strftime('%A')
    current_hour = current_time.hour
    current_minute = current_time.minute
    current_time_str = f"{current_hour:02d}:{current_minute:02d}"
    
    # Check if it's weekend
    if config.get('block_weekends', True) and current_day in ['Saturday', 'Sunday']:
        return False, f"Weekend trading blocked ({current_day})"
    
    # Check each trading window
    for window in config.get('trading_windows', []):
        # Check if current day is in allowed days
        if current_day not in window.get('days', []):
            continue
        
        start_time = window.get('start', '00:00')
        end_time = window.get('end', '23:59')
        window_name = window.get('name', 'Trading Window')
        
        # Parse start and end times
        start_hour, start_min = map(int, start_time.split(':'))
        end_hour, end_min = map(int, end_time.split(':'))
        
        # Handle overnight sessions (e.g., 13:00-03:00)
        if end_hour < start_hour:
            # Session spans midnight
            if current_hour >= start_hour or current_hour < end_hour:
                return True, f"Within {window_name} ({start_time}-{end_time} CET)"
            elif current_hour == end_hour and current_minute <= end_min:
                return True, f"Within {window_name} ({start_time}-{end_time} CET)"
        else:
            # Normal session within same day
            current_minutes = current_hour * 60 + current_minute
            start_minutes = start_hour * 60 + start_min
            end_minutes = end_hour * 60 + end_min
            
            if start_minutes <= current_minutes <= end_minutes:
                return True, f"Within {window_name} ({start_time}-{end_time} CET)"
    
    # No valid trading window found
    return False, f"Outside trading hours (Current: {current_time_str} CET)"

cycle_count = 0
# Track positions with SL moved to breakeven (eligible for trailing)
positions_at_breakeven = set()  # Set of position tickets

# Pre-calculated data cache for speed optimization
precalc_cache = {
    'account_info': None,
    'position_sizes': {},
    'spread_info': {},
    'last_update': 0
}

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
    
    # Debug: Print available columns for M5 data
    print_info(f"Available M5 columns for {symbol}: {list(df_m5.columns)}")
    
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
    
    # Volume analysis - check both real_volume and tick_volume
    print_info(f"Volume debugging for {symbol}:")
    if 'real_volume' in df_m5.columns:
        real_vol_sample = df_m5['real_volume'].tail(3).values
        print_info(f"  real_volume last 3 values: {real_vol_sample}")
    if 'tick_volume' in df_m5.columns:
        tick_vol_sample = df_m5['tick_volume'].tail(3).values
        print_info(f"  tick_volume last 3 values: {tick_vol_sample}")
    
    if 'real_volume' in df_m5.columns and df_m5['real_volume'].iloc[-1] > 0:
        current_volume = int(df_m5['real_volume'].iloc[-1])
        volume_ma = df_m5['real_volume'].rolling(window=50).mean()
        volume_ok = df_m5['real_volume'].iloc[-1] > volume_ma.iloc[-1] if len(volume_ma) >= 50 else True
        print_info(f"  Using real_volume: {current_volume}")
    elif 'tick_volume' in df_m5.columns:
        # Use tick_volume as fallback (number of ticks, not actual volume)
        current_volume = int(df_m5['tick_volume'].iloc[-1])
        volume_ma = df_m5['tick_volume'].rolling(window=50).mean()
        volume_ok = df_m5['tick_volume'].iloc[-1] > volume_ma.iloc[-1] if len(volume_ma) >= 50 else True
        print_info(f"  Using tick_volume: {current_volume}")
    else:
        current_volume = 0
        volume_ok = True
        print_info(f"  No volume data available, using 0")
    
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
            "range_low_h1": round(range_low, 5),
            "current_volume": current_volume
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

def manage_position_sl_elevation():
    """Move SL to breakeven when profit reaches configured threshold
    Also automatically places SL if none exists when profit reaches $50"""
    # Check if feature is enabled
    sl_config = RISK_MANAGEMENT_CONFIG.get('sl_to_breakeven', {})
    if not sl_config.get('enabled', True):
        return
    
    profit_threshold = sl_config.get('profit_threshold', 50)
    
    positions = mt5.positions_get()
    if not positions:
        return
    
    for position in positions:
        # Check if position has reached profit threshold
        if position.profit >= profit_threshold:
            # Check if SL is still below entry (for buy) or above entry (for sell)
            entry_price = position.price_open
            current_sl = position.sl if position.sl else 0  # Handle None or 0 SL
            
            # Get current symbol info for pip/point calculation
            symbol_info = mt5.symbol_info(position.symbol)
            if not symbol_info:
                continue
            
            # Calculate buffer based on instrument and configuration
            buffer_config = sl_config.get('buffer_pips', {})
            if "XAU" in position.symbol:
                buffer_pips = buffer_config.get('XAUUSD', 2)
                buffer = buffer_pips * 0.01  # Convert pips to price for Gold
            elif "BTC" in position.symbol:
                buffer_points = buffer_config.get('BTCUSD', 2)
                buffer = buffer_points * 1.0  # Points for Bitcoin
            else:
                buffer = 0.0002  # 2 pips for forex (default)
            
            # Determine new SL with buffer
            if position.type == mt5.POSITION_TYPE_BUY:
                new_sl = entry_price + buffer
                # Move SL if: 1) No SL exists (0), or 2) current SL is below entry (not yet at breakeven)
                if current_sl == 0 or current_sl < entry_price:
                    if current_sl == 0:
                        print_warning(f"⚠️ No SL detected for {position.symbol} BUY position - PLACING AUTOMATIC SL")
                    else:
                        print_info(f"🎯 Moving SL to breakeven for {position.symbol} BUY position")
                    print_info(f"  Entry: {entry_price:.5f} | New SL: {new_sl:.5f} | Profit: ${position.profit:.2f}")
                    if modify_position_sl(position.ticket, new_sl, position.tp if position.tp else 0):
                        print_success(f"✅ SL successfully {'placed' if current_sl == 0 else 'moved'} to breakeven + {buffer_pips if 'XAU' in position.symbol else buffer_points} {'pips' if 'XAU' in position.symbol else 'points'} buffer")
                        # Mark position as eligible for trailing stop
                        positions_at_breakeven.add(position.ticket)
            
            elif position.type == mt5.POSITION_TYPE_SELL:
                new_sl = entry_price - buffer
                # Move SL if: 1) No SL exists (0), or 2) current SL is above entry (not yet at breakeven)
                if current_sl == 0 or current_sl > entry_price:
                    if current_sl == 0:
                        print_warning(f"⚠️ No SL detected for {position.symbol} SELL position - PLACING AUTOMATIC SL")
                    else:
                        print_info(f"🎯 Moving SL to breakeven for {position.symbol} SELL position")
                    print_info(f"  Entry: {entry_price:.5f} | New SL: {new_sl:.5f} | Profit: ${position.profit:.2f}")
                    if modify_position_sl(position.ticket, new_sl, position.tp if position.tp else 0):
                        print_success(f"✅ SL successfully {'placed' if current_sl == 0 else 'moved'} to breakeven + {buffer_pips if 'XAU' in position.symbol else buffer_points} {'pips' if 'XAU' in position.symbol else 'points'} buffer")
                        # Mark position as eligible for trailing stop
                        positions_at_breakeven.add(position.ticket)

def modify_position_sl(ticket: int, new_sl: float, tp: float):
    """Modify position stop loss (and optionally TP)"""
    # Build request - only include TP if it's non-zero
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": ticket,
        "sl": new_sl,
        "magic": MAGIC_NUMBER,
        "comment": "Auto SL at $50 profit"
    }
    
    # Only add TP if it exists (non-zero)
    if tp and tp > 0:
        request["tp"] = tp
    
    result = mt5.order_send(request)
    
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        print_success(f"SL successfully updated for ticket {ticket}")
        # Log the SL modification
        log_trade(
            str(ticket), 
            "", 
            "SL_MODIFY", 
            0, 
            "", 
            new_sl, 
            tp if tp else 0, 
            status="MODIFIED", 
            reason="Auto SL: Profit >= $50 - SL set to breakeven + buffer"
        )
        return True
    else:
        error_msg = f"Failed to modify SL: {result.retcode if result else 'Unknown error'}"
        print_error(error_msg)
        return False

def detect_existing_breakeven_positions():
    """Detect positions that are already at breakeven (for bot restart scenarios)"""
    global positions_at_breakeven
    
    positions = mt5.positions_get()
    if not positions:
        return
    
    for position in positions:
        entry_price = position.price_open
        current_sl = position.sl
        
        # Check if position is likely at breakeven (SL close to entry)
        if position.type == mt5.POSITION_TYPE_BUY:
            # For BUY: SL should be at or slightly above entry
            if current_sl >= entry_price and current_sl <= (entry_price + 0.05):  # 5 pips/points tolerance
                positions_at_breakeven.add(position.ticket)
        elif position.type == mt5.POSITION_TYPE_SELL:
            # For SELL: SL should be at or slightly below entry
            if current_sl <= entry_price and current_sl >= (entry_price - 0.05):  # 5 pips/points tolerance
                positions_at_breakeven.add(position.ticket)

def manage_trailing_stops():
    """Dynamic trailing stop that activates at $60 profit with 10-pip trail"""
    global positions_at_breakeven
    
    # Check if trailing stop feature is enabled
    trailing_config = RISK_MANAGEMENT_CONFIG.get('trailing_stop', {})
    if not trailing_config.get('enabled', False):
        return
    
    positions = mt5.positions_get()
    if not positions:
        # Clean up tracking set if no positions
        positions_at_breakeven.clear()
        return
    
    # Get configuration parameters
    activation_profit = trailing_config.get('activation_profit', 60)
    trail_distances = trailing_config.get('trail_distance_points', {})
    step_size = trailing_config.get('step_size', 1)
    dynamic_mode = trailing_config.get('dynamic_mode', True)
    
    for position in positions:
        # Dynamic mode: activate trailing when profit reaches threshold
        if dynamic_mode and position.profit >= activation_profit:
            # Mark position for trailing if profit threshold reached
            if position.ticket not in positions_at_breakeven:
                positions_at_breakeven.add(position.ticket)
                print_success(f"🎯 TRAILING STOP ACTIVATED for {position.symbol} - Profit: ${position.profit:.2f}")
        
        # Skip if not ready for trailing
        if position.ticket not in positions_at_breakeven:
            continue
        
        # Get trailing distance for this instrument (10 pips for all)
        trail_distance = trail_distances.get(position.symbol, 10)
        
        # Get current market price
        tick = mt5.symbol_info_tick(position.symbol)
        if not tick:
            continue
        
        current_price = tick.bid if position.type == mt5.POSITION_TYPE_BUY else tick.ask
        current_sl = position.sl if position.sl else 0
        entry_price = position.price_open
        
        # Calculate trail distance in price terms (10 pips conversion)
        if "XAU" in position.symbol:
            # For Gold: 10 pips = 0.10 price units
            trail_distance_price = 10 * 0.01  # 10 pips = 0.10
            step_size_price = step_size * 0.01
        elif "BTC" in position.symbol:
            # For Bitcoin: 10 pips = 10 points
            trail_distance_price = 10 * 1.0  # 10 points
            step_size_price = step_size * 1.0
        else:
            # For forex: 10 pips standard
            trail_distance_price = 10 * 0.0001  # 10 pips
            step_size_price = step_size * 0.0001
        
        new_sl = None
        
        if position.type == mt5.POSITION_TYPE_BUY:
            # For BUY positions, trail SL upward
            potential_new_sl = current_price - trail_distance_price
            
            # Only move SL if:
            # 1. New SL is higher than current SL
            # 2. New SL is at least one step above current SL
            if potential_new_sl > current_sl and (potential_new_sl - current_sl) >= step_size_price:
                new_sl = potential_new_sl
        
        elif position.type == mt5.POSITION_TYPE_SELL:
            # For SELL positions, trail SL downward
            potential_new_sl = current_price + trail_distance_price
            
            # Only move SL if:
            # 1. New SL is lower than current SL
            # 2. New SL is at least one step below current SL
            if potential_new_sl < current_sl and (current_sl - potential_new_sl) >= step_size_price:
                new_sl = potential_new_sl
        
        # Execute the trailing stop adjustment
        if new_sl:
            profit_pips = abs(current_price - entry_price) / (0.01 if 'XAU' in position.symbol else 1.0 if 'BTC' in position.symbol else 0.0001)
            print_info(f"🔄 DYNAMIC TRAILING STOP UPDATE for {position.symbol} {('BUY' if position.type == mt5.POSITION_TYPE_BUY else 'SELL')}")
            print_info(f"  Profit: ${position.profit:.2f} | Movement: {profit_pips:.1f} pips")
            print_info(f"  Current Price: {current_price:.5f} | Old SL: {current_sl:.5f} | New SL: {new_sl:.5f}")
            print_info(f"  Trail Distance: 10 pips (keeping profit locked)")
            
            if modify_trailing_sl(position.ticket, new_sl, position.tp if position.tp else 0, position.symbol):
                print_success(f"✅ Dynamic trailing stop updated - protecting ${position.profit:.2f} profit")

def modify_trailing_sl(ticket: int, new_sl: float, tp: float, symbol: str):
    """Modify position stop loss for dynamic trailing"""
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": ticket,
        "sl": new_sl,
        "magic": MAGIC_NUMBER,
        "comment": "Dynamic trail @$60"
    }
    
    # Only add TP if it exists
    if tp and tp > 0:
        request["tp"] = tp
    
    result = mt5.order_send(request)
    
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        # Log the trailing SL modification
        log_trade(
            str(ticket), 
            symbol, 
            "TRAILING_SL", 
            0, 
            "", 
            new_sl, 
            tp, 
            status="MODIFIED", 
            reason="Trailing stop adjustment"
        )
        return True
    else:
        error_msg = f"Failed to modify trailing SL: {result.retcode if result else 'Unknown error'}"
        print_error(error_msg)
        return False

def update_precalc_cache(force_update=False):
    """Update pre-calculated cache for speed optimization"""
    global precalc_cache
    
    exec_config = SYSTEM_CONFIG.get('execution_optimization', {})
    if not exec_config.get('pre_calculate_sizes', True) and not force_update:
        return
    
    current_time = time.time()
    # Update cache every 30 seconds or on force
    if current_time - precalc_cache['last_update'] < 30 and not force_update:
        return
    
    try:
        # Get fresh account info
        account = mt5.account_info()
        if account:
            precalc_cache['account_info'] = account
            
            # Calculate dynamic lot sizes based on account equity
            for symbol in TRADING_INSTRUMENTS:
                lot_size = calculate_lot_size(symbol, account.equity)
                precalc_cache['position_sizes'][symbol] = lot_size
                
                # Cache spread info
                tick = mt5.symbol_info_tick(symbol)
                if tick:
                    spread = tick.ask - tick.bid
                    precalc_cache['spread_info'][symbol] = {
                        'spread': spread,
                        'ask': tick.ask,
                        'bid': tick.bid,
                        'timestamp': current_time
                    }
        
        precalc_cache['last_update'] = current_time
        
    except Exception as e:
        print_error(f"Failed to update precalc cache: {e}")

def auto_refresh_open_trades(signals: list):
    """Auto-refresh only closes positions when signal direction changes - NO SL/TP updates"""
    positions = mt5.positions_get()
    if not positions:
        print_info("📊 No open positions - Ready for new opportunities")
        return
    
    print_separator()
    print_info("🔄 POSITION MONITORING - Checking for direction changes only")
    print_info(f"   Active positions: {len(positions)} | SL/TP updates DISABLED")
    
    for position in positions:
        symbol = position.symbol
        current_type = "BUY" if position.type == mt5.POSITION_TYPE_BUY else "SELL"
        
        # Find matching signal for this symbol
        matching_signal = None
        for signal in signals:
            if signal["symbol"] == symbol and signal["action"] in ["BUY", "SELL"]:
                matching_signal = signal
                break
        
        if not matching_signal:
            print_info(f"  {symbol}: No actionable signal - maintaining current {current_type} position")
            continue
        
        new_action = matching_signal["action"]
        
        # ONLY ACTION: Check if direction changed (close trade)
        if current_type != new_action:
            print_warning(f"⚠️ SIGNAL REVERSAL DETECTED for {symbol}: {current_type} → {new_action}")
            print_info(f"  Closing existing {current_type} position immediately")
            
            close_request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": position.ticket,
                "symbol": symbol,
                "volume": position.volume,
                "type": mt5.ORDER_TYPE_SELL if position.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                "magic": MAGIC_NUMBER,
                "comment": "Signal reversal",
                "type_filling": mt5.ORDER_FILLING_IOC
            }
            
            result = mt5.order_send(close_request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                print_success(f"✅ Closed {symbol} position due to signal reversal")
                log_trade(
                    str(result.deal or position.ticket),
                    symbol,
                    "CLOSE",
                    matching_signal.get("confidence", 0),
                    "",
                    "",
                    "",
                    status="AUTO_CLOSED",
                    reason=f"Signal reversal: {current_type} -> {new_action}"
                )
            else:
                print_error(f"❌ Failed to close {symbol} position: {result.retcode if result else 'Unknown error'}")
        else:
            # Same direction - NO ACTION on SL/TP
            print_info(f"  {symbol}: Signal still {current_type} - position maintained (SL/TP unchanged)")

def get_precalc_lot_size(symbol: str) -> float:
    """Get pre-calculated lot size for fast execution"""
    # Use cached value if available and recent
    if symbol in precalc_cache['position_sizes']:
        return precalc_cache['position_sizes'][symbol]
    
    # Fallback to real-time calculation
    account = precalc_cache.get('account_info') or mt5.account_info()
    if account:
        return calculate_lot_size(symbol, account.equity)
    
    return 0.01  # Minimum fallback

def get_precalc_spread_info(symbol: str) -> dict:
    """Get pre-calculated spread info for fast execution"""
    spread_info = precalc_cache['spread_info'].get(symbol, {})
    
    # Return cached if recent (less than 10 seconds old)
    if spread_info and (time.time() - spread_info.get('timestamp', 0)) < 10:
        return spread_info
    
    # Get fresh data if cache is stale
    tick = mt5.symbol_info_tick(symbol)
    if tick:
        return {
            'spread': tick.ask - tick.bid,
            'ask': tick.ask,
            'bid': tick.bid,
            'timestamp': time.time()
        }
    
    return {}

def calculate_lot_size(symbol: str, account_equity: float) -> float:
    """Calculate dynamic lot size based on capital: min 1 lot, +/-0.5 per $5000 capital change"""
    
    # Get dynamic lot sizing configuration
    lot_config = RISK_MANAGEMENT_CONFIG['dynamic_lot_sizing']
    
    if not lot_config.get('enabled', True):
        return lot_config.get('base_lot_size', 1.0)
    
    # Get configuration parameters
    base_lot_size = lot_config.get('base_lot_size', 1.0)
    starting_capital = lot_config.get('starting_capital', 10000.0)
    capital_increment = lot_config.get('capital_increment', 5000.0)
    lot_increment = lot_config.get('lot_increment', 0.5)
    min_lot_size = lot_config.get('min_lot_size', 1.0)
    
    # Calculate capital change from starting point
    capital_change = account_equity - starting_capital
    
    # Calculate additional lots based on configured increments
    additional_lots = (capital_change / capital_increment) * lot_increment
    
    # Calculate final lot size
    final_lot_size = base_lot_size + additional_lots
    
    # Ensure minimum lot size
    final_lot_size = max(min_lot_size, final_lot_size)
    
    # Round to 1 decimal place for practical lot sizes
    return round(final_lot_size, 1)

def adjust_tp_sl(symbol: str, entry: float, sl: float, tp: float, support_resistance: dict = None, atr: float = None) -> tuple:
    """Adjust TP and SL based on ATR-ADJUSTED RULES:
    BTCUSD:
        BUY: SL = Entry - max(40 pips, 1×ATR), TP = Entry + max(65 pips, 1.5×ATR)
        SELL: SL = Entry + max(40 pips, 1×ATR), TP = Entry - max(65 pips, 1.5×ATR)
    XAUUSD:
        BUY: SL = Entry - max(70 pips, 1×ATR), TP = Entry + max(140 pips, 1.5×ATR)
        SELL: SL = Entry + max(70 pips, 1×ATR), TP = Entry - max(140 pips, 1.5×ATR)
    """
    
    # Determine if BUY or SELL based on original SL position from DeepSeek
    is_buy = sl < entry
    
    # Get ATR value if not provided
    if atr is None:
        # Try to get ATR from MT5 (fallback to fixed values if not available)
        print_warning("  [ATR] No ATR provided, using minimum fixed values")
        atr = 0
    
    # Apply ATR-adjusted rules based on instrument
    if 'BTC' in symbol:
        # BTCUSD: 1 pip = 1 point
        pip_value = 1.0
        
        # Calculate ATR-based values
        atr_sl = 1.0 * atr  # 1×ATR
        atr_tp = 1.5 * atr  # 1.5×ATR
        
        # Minimum fixed values in price units
        min_sl_pips = 40
        min_tp_pips = 65
        
        # Take maximum between fixed and ATR-based
        sl_distance = max(min_sl_pips * pip_value, atr_sl)
        tp_distance = max(min_tp_pips * pip_value, atr_tp)
        
        if is_buy:
            # BUY: SL below entry, TP above entry
            final_sl = entry - sl_distance
            final_tp = entry + tp_distance
            print_info(f"  [ATR-ADJUSTED] {symbol} BUY:")
            print_info(f"    ATR={atr:.2f}, 1×ATR={atr_sl:.2f}, 1.5×ATR={atr_tp:.2f}")
            print_info(f"    SL distance: max(40, {atr_sl:.2f}) = {sl_distance:.2f}")
            print_info(f"    TP distance: max(65, {atr_tp:.2f}) = {tp_distance:.2f}")
            print_info(f"    Final: SL={final_sl:.2f}, TP={final_tp:.2f}")
        else:
            # SELL: SL above entry, TP below entry
            final_sl = entry + sl_distance
            final_tp = entry - tp_distance
            print_info(f"  [ATR-ADJUSTED] {symbol} SELL:")
            print_info(f"    ATR={atr:.2f}, 1×ATR={atr_sl:.2f}, 1.5×ATR={atr_tp:.2f}")
            print_info(f"    SL distance: max(40, {atr_sl:.2f}) = {sl_distance:.2f}")
            print_info(f"    TP distance: max(65, {atr_tp:.2f}) = {tp_distance:.2f}")
            print_info(f"    Final: SL={final_sl:.2f}, TP={final_tp:.2f}")
            
        # Calculate Risk/Reward
        rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0
        print_info(f"  [ATR-ADJUSTED] Risk/Reward Ratio: 1:{rr_ratio:.2f}")
        
    elif 'XAU' in symbol:
        # XAUUSD: 1 pip = 0.01 for Gold
        pip_value = 0.01
        
        # Calculate ATR-based values
        atr_sl = 1.0 * atr  # 1×ATR
        atr_tp = 1.5 * atr  # 1.5×ATR
        
        # Minimum fixed values in price units
        min_sl_pips = 70
        min_tp_pips = 140
        
        # Take maximum between fixed and ATR-based (convert pips to price)
        sl_distance = max(min_sl_pips * pip_value, atr_sl)
        tp_distance = max(min_tp_pips * pip_value, atr_tp)
        
        if is_buy:
            # BUY: SL below entry, TP above entry
            final_sl = entry - sl_distance
            final_tp = entry + tp_distance
            print_info(f"  [ATR-ADJUSTED] {symbol} BUY:")
            print_info(f"    ATR={atr:.2f}, 1×ATR={atr_sl:.2f}, 1.5×ATR={atr_tp:.2f}")
            print_info(f"    SL distance: max({min_sl_pips*pip_value:.2f}, {atr_sl:.2f}) = {sl_distance:.2f}")
            print_info(f"    TP distance: max({min_tp_pips*pip_value:.2f}, {atr_tp:.2f}) = {tp_distance:.2f}")
            print_info(f"    Final: SL={final_sl:.2f}, TP={final_tp:.2f}")
        else:
            # SELL: SL above entry, TP below entry
            final_sl = entry + sl_distance
            final_tp = entry - tp_distance
            print_info(f"  [ATR-ADJUSTED] {symbol} SELL:")
            print_info(f"    ATR={atr:.2f}, 1×ATR={atr_sl:.2f}, 1.5×ATR={atr_tp:.2f}")
            print_info(f"    SL distance: max({min_sl_pips*pip_value:.2f}, {atr_sl:.2f}) = {sl_distance:.2f}")
            print_info(f"    TP distance: max({min_tp_pips*pip_value:.2f}, {atr_tp:.2f}) = {tp_distance:.2f}")
            print_info(f"    Final: SL={final_sl:.2f}, TP={final_tp:.2f}")
            
        # Calculate Risk/Reward
        rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0
        print_info(f"  [ATR-ADJUSTED] Risk/Reward Ratio: 1:{rr_ratio:.2f}")
        
    else:
        # Fallback for other symbols
        print_warning(f"  Unknown symbol {symbol}, using original SL/TP")
        final_sl = sl
        final_tp = tp
    
    return final_sl, final_tp

def open_trade_fast(symbol: str, action: str, sl: float, tp: float, key_levels: dict = None, atr: float = None):
    """Optimized trade execution with pre-calculated data and 5s timeout"""
    exec_config = SYSTEM_CONFIG.get('execution_optimization', {})
    execution_timeout = exec_config.get('trade_execution_timeout', 5)
    max_retries = exec_config.get('retry_attempts', 2)
    
    start_time = time.time()
    
    try:
        ensure_symbol(symbol)
        
        # Use pre-calculated spread info for speed
        spread_info = get_precalc_spread_info(symbol)
        if not spread_info:
            print_error(f"Failed to get market data for {symbol}")
            return None
        
        if action.upper() == "BUY":
            price = spread_info['ask']
            otype = mt5.ORDER_TYPE_BUY
        elif action.upper() == "SELL":
            price = spread_info['bid']
            otype = mt5.ORDER_TYPE_SELL
        else:
            return None
        
        # Use pre-calculated lot size
        volume = get_precalc_lot_size(symbol)
        
        # Get ATR if not provided
        if atr is None:
            # Try to get H1 ATR
            rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)
            if rates_h1 is not None and len(rates_h1) >= 14:
                df_h1 = pd.DataFrame(rates_h1)
                high = df_h1['high']
                low = df_h1['low']
                close = df_h1['close']
                tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
                atr = tr.rolling(window=14).mean().iloc[-1]
                print_info(f"  [ATR] Calculated H1 ATR(14): {atr:.2f}")
            else:
                atr = 0
                print_warning("  [ATR] Could not calculate ATR, using minimum fixed values")
        
        # Adjust TP/SL based on configuration with ATR
        adjusted_sl, adjusted_tp = adjust_tp_sl(symbol, price, sl, tp, key_levels, atr)
        
        # Optimized order request
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": otype,
            "price": price,
            "sl": adjusted_sl,
            "tp": adjusted_tp,
            "deviation": exec_config.get('slippage_tolerance', 3),
            "magic": MAGIC_NUMBER,
            "comment": "Thanatos AI Bot - Fast",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        print_info(f"⚡ Fast execution: {action} {symbol} @ {price:.5f}")
        print_info(f"  Volume: {volume} lots | SL: {adjusted_sl:.5f} | TP: {adjusted_tp:.5f}")
        
        # Execute with timeout and retries
        for attempt in range(max_retries + 1):
            if time.time() - start_time > execution_timeout:
                print_error(f"❌ Trade execution timeout ({execution_timeout}s)")
                return None
            
            print_info(f"Executing trade (attempt {attempt + 1}/{max_retries + 1})...")
            res = mt5.order_send(req)
            
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                execution_time = time.time() - start_time
                print_success(f"✅ Order executed in {execution_time:.2f}s! Ticket: {res.order}")
                return res
            elif res and res.retcode in [mt5.TRADE_RETCODE_REQUOTE, mt5.TRADE_RETCODE_PRICE_OFF]:
                # Price changed, get fresh quote and retry
                if attempt < max_retries:
                    print_warning(f"Price changed, retrying... ({res.retcode})")
                    tick = mt5.symbol_info_tick(symbol)
                    if tick:
                        req["price"] = tick.ask if action.upper() == "BUY" else tick.bid
                    time.sleep(0.1)  # Brief pause before retry
                    continue
            
            # Other errors
            if res:
                print_error(f"❌ Order failed: {res.retcode}")
            else:
                print_error("❌ Order failed: Unknown error")
            
            if attempt < max_retries:
                time.sleep(0.2)  # Brief pause before retry
        
        return None
        
    except Exception as e:
        print_error(f"❌ Fast execution error: {e}")
        return None

def open_trade(symbol: str, action: str, sl: float, tp: float, key_levels: dict = None, atr: float = None):
    """Standard trade execution (fallback or when fast mode disabled)"""
    exec_config = SYSTEM_CONFIG.get('execution_optimization', {})
    
    # Use fast execution if enabled
    if exec_config.get('fast_mode', True):
        return open_trade_fast(symbol, action, sl, tp, key_levels, atr)
    
    # Standard execution path
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
    
    # Calculate lot size based on risk management
    volume = calculate_lot_size(symbol, account.equity)
    
    # Display lot sizing calculation details
    lot_config = RISK_MANAGEMENT_CONFIG['dynamic_lot_sizing']
    starting_capital = lot_config.get('starting_capital', 10000.0)
    capital_change = account.equity - starting_capital
    print_info(f"Dynamic Lot Sizing: Equity ${account.equity:.2f} | Change: ${capital_change:+.2f} | Lot: {volume}")
    
    # Get ATR if not provided
    if atr is None:
        # Try to get H1 ATR
        rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)
        if rates_h1 is not None and len(rates_h1) >= 14:
            df_h1 = pd.DataFrame(rates_h1)
            high = df_h1['high']
            low = df_h1['low']
            close = df_h1['close']
            tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
            atr = tr.rolling(window=14).mean().iloc[-1]
            print_info(f"  [ATR] Calculated H1 ATR(14): {atr:.2f}")
        else:
            atr = 0
            print_warning("  [ATR] Could not calculate ATR, using minimum fixed values")
    
    # Adjust TP/SL based on configuration with ATR
    adjusted_sl, adjusted_tp = adjust_tp_sl(symbol, price, sl, tp, key_levels, atr)
    
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": otype,
        "price": price,
        "sl": adjusted_sl,
        "tp": adjusted_tp,
        "deviation": DEVIATION,
        "magic": MAGIC_NUMBER,
        "comment": "Thanatos AI Bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    print_info(f"Sending order: {action} {symbol} @ {price:.5f}")
    print_info(f"  Volume: {volume} lots")
    print_info(f"  Adjusted SL: {adjusted_sl:.5f} (from {sl:.5f})")
    print_info(f"  Adjusted TP: {adjusted_tp:.5f} (from {tp:.5f})")
    res = mt5.order_send(req)
    
    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
        print_success(f"Order executed! Ticket: {res.order}")
    else:
        print_error(f"Order failed: {res.retcode if res else 'Unknown error'}")
    
    return res

def get_instrument_specific_instructions(symbol: str) -> str:
    """Get instrument-specific analysis instructions"""
    instructions = PROMPT_CONFIG.get('specific_instructions', {}).get(symbol, [])
    instrument_config = get_instrument_config(symbol)
    tp_sl_config = get_tp_sl_adjustment(symbol)
    
    prompt_section = f"=== INSTRUMENT-SPECIFIC PARAMETERS FOR {symbol} ===\n"
    prompt_section += f"Type: {instrument_config.get('type', 'unknown').upper()}\n"
    prompt_section += f"Volatility: {instrument_config.get('volatility', 'medium').upper()}\n"
    prompt_section += f"TP Reduction Factor: {tp_sl_config.get('tp_reduction_factor', 0.7)}\n"
    prompt_section += f"SL Increase Factor: {tp_sl_config.get('sl_increase_factor', 1.2)}\n"
    prompt_section += f"Min Risk/Reward: {tp_sl_config.get('min_risk_reward_ratio', 1.5)}\n"
    
    if symbol == "XAUUSD":
        prompt_section += "\nGOLD-SPECIFIC ANALYSIS REQUIRED:\n"
        prompt_section += "- Gold is a safe-haven asset, reacts strongly to USD strength\n"
        prompt_section += "- Consider DXY inversely correlated (DXY up = Gold down)\n"
        prompt_section += "- Key psychological levels: 2000, 2050, 2100\n"
        prompt_section += "- Higher weight on H1 timeframe due to institutional flows\n"
        prompt_section += "- Conservative approach: Require stronger confluence\n"
    elif symbol == "BTCUSD":
        prompt_section += "\nBITCOIN-SPECIFIC ANALYSIS REQUIRED:\n"
        prompt_section += "- Bitcoin is highly volatile cryptocurrency\n"
        prompt_section += "- 24/7 trading, weekend gaps common\n"
        prompt_section += "- Key psychological levels: 100000, 95000, 90000\n"
        prompt_section += "- Volume analysis critical - low volume = false breakouts\n"
        prompt_section += "- More aggressive on momentum but strict on range detection\n"
    
    if instructions:
        prompt_section += "\nAdditional Considerations:\n"
        for instruction in instructions:
            prompt_section += f"  - {instruction}\n"
    
    return prompt_section

def check_tolerant_maxprotect(technical_data: dict, tolerance_config: dict) -> bool:
    """
    Check MaxProtect with tolerant rules
    Returns True if MaxProtect passes (trading allowed)
    """
    try:
        # Extract trend directions from technical data
        h1_trend = technical_data.get('timeframes', {}).get('H1', {}).get('trend', 'unknown')
        m15_trend = technical_data.get('timeframes', {}).get('M15', {}).get('trend', 'unknown')
        m5_trend = technical_data.get('timeframes', {}).get('M5', {}).get('trend', 'unknown')
        
        # Convert trend strings to simplified direction
        def simplify_trend(trend):
            trend_lower = str(trend).lower()
            if 'bullish' in trend_lower or 'up' in trend_lower:
                return 'up'
            elif 'bearish' in trend_lower or 'down' in trend_lower:
                return 'down'
            else:
                return 'neutral'
        
        h1_dir = simplify_trend(h1_trend)
        m15_dir = simplify_trend(m15_trend)
        m5_dir = simplify_trend(m5_trend)
        
        # Count conflicts
        conflicts = 0
        if h1_dir != 'neutral' and m15_dir != 'neutral' and h1_dir != m15_dir:
            conflicts += 1
        if h1_dir != 'neutral' and m5_dir != 'neutral' and h1_dir != m5_dir:
            conflicts += 1
        if m15_dir != 'neutral' and m5_dir != 'neutral' and m15_dir != m5_dir:
            conflicts += 1
        
        # Apply tolerant rules
        if tolerance_config.get('allow_one_conflict', True):
            # Allow trading with up to 1 conflict
            if conflicts <= 1:
                return True
        
        if tolerance_config.get('require_major_alignment', True):
            # Only require H1 and M15 to align (ignore M5)
            if h1_dir != 'neutral' and m15_dir != 'neutral':
                if h1_dir == m15_dir:
                    return True
        
        # If no conflicts at all, always pass
        if conflicts == 0:
            return True
        
        # Default: fail if 2+ conflicts
        return conflicts < 2
        
    except Exception as e:
        print_warning(f"MaxProtect check error: {e} - defaulting to PASS")
        return True  # Default to pass on error to be tolerant

def deepseek_analyze(symbol: str, technical_data: dict, account_info) -> dict:
    """Use the Thanatos-Guardian-Prime prompt"""
    headers = {"Authorization": f"Bearer {LLM_KEY}", "Content-Type":"application/json"}
    
    # Check news
    blocked, reason = is_blocked_now(symbol)
    red_news_window = blocked
    
    # UK close check removed - no longer blocking trades after UK close
    now = datetime.now()
    uk_close_block = False  # Disabled UK close protection
    
    # MaxProtect reactivated with tolerant rules
    
    # Determine session weight for adaptive confidence
    session_weight = 0
    if technical_data['sessions']['active'] == "New York" and technical_data['sessions']['ny_open_boost']:
        session_weight = 3
    elif technical_data['sessions']['active'] == "London":
        session_weight = 2
    elif technical_data['sessions']['active'] == "Asian":
        session_weight = -2
    
    # Get instrument-specific characteristics
    instrument_config = get_instrument_config(symbol)
    instrument_type = instrument_config.get('type', 'unknown')
    volatility_profile = instrument_config.get('volatility', 'medium')
    
    # Build the enhanced prompt with new template
    prompt = f"""=== CURRENT MARKET DATA ===
SYMBOL: {symbol}
INSTRUMENT TYPE: {instrument_type.upper()}
VOLATILITY PROFILE: {volatility_profile.upper()}
TIME: {technical_data['timestamp_cet']} CET
SESSION: {technical_data['sessions']['active']} ({session_weight:+d}% confidence boost)
CURRENT PRICE: {technical_data['price']}

=== TECHNICAL INDICATORS ===
ADX H1: {technical_data['measures']['adx14_h1']}
ATR H1: {technical_data['measures']['atr_h1_points']} points ({technical_data['measures']['atr_h1_pct']:.2f}%)
BB Width H1: {technical_data['measures']['bb20_width_pct_h1']:.2f}%
Range High H1: {technical_data['measures']['range_high_h1']}
Range Low H1: {technical_data['measures']['range_low_h1']}
Inside Lookback H1: {technical_data['measures']['inside_lookback_h1']} candles

=== MULTI-TIMEFRAME STRUCTURE ===
H1 TREND: {technical_data['mtf_state']['H1_trend']}
M15 TREND: {technical_data['mtf_state']['M15_trend']}
M5 SETUP: {technical_data['mtf_state']['M5_setup']}
VOLUME OK: {technical_data['mtf_state']['volume_ok']}
OBV AGREES: {technical_data['mtf_state']['obv_agrees']}

=== RISK & SAFETY ===
Active Trades: {len(open_positions_map())}
Equity: ${account_info.equity:.2f}
News Window: {'🔴 BLOCKED' if red_news_window else '✅ CLEAR'}

{get_instrument_specific_instructions(symbol)}

=== INSTRUCTIONS ===
Analyze this data using Thanatos-Guardian-Prime v15.2-MAXPROTECT protocol.
Apply adaptive session weight: {session_weight:+d}% for {technical_data['sessions']['active']}.
Respect minimum confidence threshold: 70%.
TRIPLE VALIDATION REQUIRED.
MaxProtect: ACTIVE but TOLERANT - Allows 1 timeframe conflict, requires H1/M15 alignment only.

IMPORTANT: Confidence must reflect instrument-specific characteristics:
- XAUUSD (Gold): More conservative, requires stronger confluence (typically 70-85% range)
- BTCUSD (Bitcoin): Can be more aggressive on momentum (can reach 85-95% on strong setups)
- Each instrument should have DIFFERENT confidence based on their unique market conditions
- DO NOT give similar confidence to both instruments unless conditions truly warrant it

RESPOND ONLY IN STRICT YAML FORMAT:

visual_signal:
  triple_check_status: "✅ VALIDATED 3×" or "⛔️ NOT VALIDATED"
  action: "BUY" or "SELL" or "NO_TRADE"
  confidence:
    value: <float 0-100>
    level: "😊" if >=90 | "😃" if 85-89 | "🙂" if 70-84 | "⛔" if <70
    breakdown:
      quantum: <float 0-100>
      tactical: <float 0-100>
      psychological: <float 0-100>
    adaptive_note: "Session {technical_data['sessions']['active']} ({session_weight:+d}% confidence)"
  alerts: <list of alerts>

execution_plan:
  entry: <float>
  sl: <float>
  tp1: <float>
  tp2: <float>
  tp3: <float>
  rr_ratios:
    tp1_rr: <float>
    tp2_rr: <float>
    tp3_rr: <float>
  time_projection: <string>

guardian_filters:
  mandatory_confluence:
    session_ok: <true/false with description>
    structure_ok: <true/false with description>
    flow_ok: <true/false with description>
  hard_safety: <string status>
  soft_safety: <list of checks>

max_protect_rule:
  description: "If >=2 trends conflict between H1/M15/M5 -> FORCE NO_TRADE"
  status: <string>

pair_profile:
  current_status: <string>
  kill_zones: <string>

optimization_data:
  potential_setup: <string>
  key_levels:
    support: <float>
    resistance: <float>
  volume_trigger: <string>

analysis: <string explaining the decision>
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
        "ADX_threshold": {"value": technical_data['measures']['adx14_h1'], "required": 15, "passed": technical_data['measures']['adx14_h1'] > 15},
        "ATR_threshold": {"value": technical_data['measures']['atr_h1_pct'], "required": 0.25, "passed": technical_data['measures']['atr_h1_pct'] >= 0.25},
        "BB_width_threshold": {"value": technical_data['measures']['bb20_width_pct_h1'], "required": 0.4, "passed": technical_data['measures']['bb20_width_pct_h1'] >= 0.4},
        "consolidation_check": {"inside_bars": technical_data['measures']['inside_lookback_h1'], "max_allowed": 20, "passed": technical_data['measures']['inside_lookback_h1'] < 20},
        "news_filter": {"blocked": red_news_window, "reason": reason if red_news_window else "Clear"},
        "uk_close_filter": {"blocked": False, "time": f"{now.hour}:{now.minute:02d}", "status": "DISABLED"},
        "active_trades": {"count": len(open_positions_map()), "max_allowed": 2, "passed": len(open_positions_map()) < 2},
        "session": technical_data['sessions']['active'],
        "ny_open_boost": technical_data['sessions']['ny_open_boost'],
        "H1_trend": technical_data['mtf_state']['H1_trend'],
        "M15_trend": technical_data['mtf_state']['M15_trend'],
        "M5_setup": technical_data['mtf_state']['M5_setup'],
        "volume_ok": technical_data['mtf_state']['volume_ok'],
        "min_confidence_required": MIN_CONFIDENCE
    }
    
    print_info("Requesting Thanatos-Guardian-Prime analysis...")
    # Retry logic for timeout errors
    max_retries = 2
    for attempt in range(max_retries):
        try:
            # Increased timeout to 60 seconds to handle longer processing times
            r = requests.post(LLM_URL, headers=headers, json=payload, timeout=60)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            break
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                print_warning(f"API timeout, retrying... (attempt {attempt + 2}/{max_retries})")
                time.sleep(2)
            else:
                print_error("API timeout after all retries")
                raise
        except Exception as e:
            print_error(f"API request failed: {e}")
            raise
    
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
        
        # Convert new format to expected format
        if 'visual_signal' in parsed:
            # Extract data from new format
            visual_signal = parsed.get('visual_signal', {})
            execution_plan = parsed.get('execution_plan', {})
            guardian_filters = parsed.get('guardian_filters', {})
            max_protect = parsed.get('max_protect_rule', {})
            optimization = parsed.get('optimization_data', {})
            
            # Build response in expected format
            converted_response = {
                "action": visual_signal.get('action', 'NO_TRADE'),
                "confidence": visual_signal.get('confidence', {}).get('value', 0),
                "confidence_breakdown": visual_signal.get('confidence', {}).get('breakdown', {}),
                "entry": execution_plan.get('entry'),
                "sl": execution_plan.get('sl'),
                "tp1": execution_plan.get('tp1'),
                "tp2": execution_plan.get('tp2'),
                "tp3": execution_plan.get('tp3'),
                "rr_ratios": execution_plan.get('rr_ratios', {}),
                "time_projection": execution_plan.get('time_projection', ''),
                "analysis": parsed.get('analysis', ''),
                "guardian_status": {
                    "anti_range_pass": 'NOT VALIDATED' not in visual_signal.get('triple_check_status', ''),
                    "confluence_pass": guardian_filters.get('mandatory_confluence', {}).get('structure_ok', False),
                    "max_protect_pass": check_tolerant_maxprotect(technical_data, {
                        'allow_one_conflict': True,
                        'require_major_alignment': True,
                        'spread_check': False,
                        'volume_requirement': 'relaxed'
                    }),
                    "session_ok": guardian_filters.get('mandatory_confluence', {}).get('session_ok', False),
                    "structure_ok": guardian_filters.get('mandatory_confluence', {}).get('structure_ok', False),
                    "flow_ok": guardian_filters.get('mandatory_confluence', {}).get('flow_ok', False)
                },
                "alerts": visual_signal.get('alerts', []),
                "key_levels": optimization.get('key_levels', {})
            }
            
            # Log the prompt and analysis
            log_analysis_prompt(symbol, prompt, checked_rules, parsed)
            
            return converted_response
        else:
            # Old format, use as-is
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
                "max_protect_pass": False  # Failed to parse, assume fail
            }
        }
        
        # Log even failed parsing attempts
        log_analysis_prompt(symbol, prompt, checked_rules, {"error": str(e), "raw_content": content})
        
        return safe_response

def cycle_once():
    global cycle_count
    cycle_count += 1
    
    print_cycle_start(cycle_count)
    
    # Check and display trading hours status
    hours_allowed, hours_reason = is_trading_hours_allowed()
    if hours_allowed:
        print_info(f"[TRADING HOURS] {Colors.GREEN}ACTIVE{Colors.RESET} - {hours_reason}")
    else:
        print_warning(f"[TRADING HOURS] {Colors.RED}BLOCKED{Colors.RESET} - {hours_reason}")
    
    # Update pre-calculation cache for speed optimization
    update_precalc_cache()
    
    # Get account info (use cached if available)
    account = precalc_cache.get('account_info') or mt5.account_info()
    if not account:
        print_error("Failed to get account info")
        return
    
    # Get current positions
    open_pos = open_positions_map()
    print_position_status(open_pos)
    
    # Manage existing positions - check for SL elevation and trailing stops
    if open_pos:
        print_separator()
        print_info("Checking positions for SL elevation...")
        manage_position_sl_elevation()
        
        print_info("Managing trailing stops...")
        manage_trailing_stops()
        
        # Show trailing status
        if positions_at_breakeven:
            print_info(f"Positions eligible for trailing: {len(positions_at_breakeven)}")
    
    # Check if we have max trades (but still continue with analysis for auto-refresh)
    max_trades = RISK_MANAGEMENT_CONFIG['max_concurrent_trades']
    if len(open_pos) >= max_trades:
        print_info(f"Maximum trades ({max_trades}) already open. Continuing analysis for position management...")
    
    # Check news
    print_separator()
    blocked_pairs = {}
    for symbol in PAIRS:
        blocked, reason = is_blocked_now(symbol)
        if blocked:
            blocked_pairs[symbol] = reason
    print_news_status(blocked_pairs)
    
    # Analyze each pair (always analyze all for continuous market adaptation)
    print_separator()
    print_info("🔍 PERFORMING DEEP MARKET ANALYSIS FOR ALL INSTRUMENTS")
    print_info("   (Continuous adaptation for both new and existing positions)")
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
                "volume": tech_data['measures']['current_volume']
            })
            
            # Display technical indicators
            print(f"  {Colors.WHITE}ADX(14): {Colors.CYAN}{tech_data['measures']['adx14_h1']}{Colors.RESET}")
            print(f"  {Colors.WHITE}ATR%: {Colors.CYAN}{tech_data['measures']['atr_h1_pct']:.2f}%{Colors.RESET}")
            print(f"  {Colors.WHITE}BB Width%: {Colors.CYAN}{tech_data['measures']['bb20_width_pct_h1']:.2f}%{Colors.RESET}")
            print(f"  {Colors.WHITE}H1 Trend: {Colors.CYAN}{tech_data['mtf_state']['H1_trend']}{Colors.RESET}")
            print(f"  {Colors.WHITE}Session: {Colors.CYAN}{tech_data['sessions']['active']}{Colors.RESET}")
            
            # Get AI analysis
            analysis = deepseek_analyze(symbol, tech_data, account)
            
            # Add to signals list with new fields
            signals.append({
                "symbol": symbol,
                "action": analysis.get("action", "NO_TRADE"),
                "confidence": float(analysis.get("confidence", 0)),
                "confidence_breakdown": analysis.get("confidence_breakdown", {}),
                "entry": analysis.get("entry"),
                "sl": analysis.get("sl"),
                "tp": analysis.get("tp1"),  # Use first TP
                "tp2": analysis.get("tp2"),
                "tp3": analysis.get("tp3"),
                "rr_ratios": analysis.get("rr_ratios", {}),
                "time_projection": analysis.get("time_projection", ""),
                "analysis": analysis.get("analysis", ""),
                "guardian": analysis.get("guardian_status", {}),
                "alerts": analysis.get("alerts", []),
                "key_levels": analysis.get("key_levels", {}),
                "atr": tech_data['measures']['atr_h1_points']  # Include ATR for SL/TP adjustment
            })
            
        except Exception as e:
            print_error(f"Error analyzing {symbol}: {e}")
            continue
    
    # Process signals (highest confidence first)
    signals = sorted(signals, key=lambda x: x["confidence"], reverse=True)
    
    # Auto-refresh existing trades with new signals
    auto_refresh_open_trades(signals)
    
    for sig in signals:
        symbol = sig["symbol"]
        action = sig["action"].upper()
        confidence = sig["confidence"]
        
        # Display AI analysis
        print_ai_analysis(
            symbol, action, confidence,
            sig.get("entry"), sig.get("sl"), sig.get("tp")
        )
        
        # Display confidence breakdown if available
        breakdown = sig.get("confidence_breakdown", {})
        if breakdown:
            # Determine confidence emoji
            conf_emoji = "😊" if confidence >= 90 else "😃" if confidence >= 85 else "🙂" if confidence >= 70 else "⛔"
            print(f"  {Colors.WHITE}Confidence: {Colors.CYAN}{confidence}% {conf_emoji}{Colors.RESET}")
            print(f"  {Colors.WHITE}Confidence Breakdown:{Colors.RESET}")
            print(f"    Quantum: {Colors.CYAN}{breakdown.get('quantum', 0)}%{Colors.RESET}")
            print(f"    Tactical: {Colors.CYAN}{breakdown.get('tactical', 0)}%{Colors.RESET}")
            print(f"    Psychological: {Colors.CYAN}{breakdown.get('psychological', 0)}%{Colors.RESET}")
            if breakdown.get('session_adjustment'):
                adj_color = Colors.GREEN if breakdown['session_adjustment'] > 0 else Colors.YELLOW if breakdown['session_adjustment'] < 0 else Colors.WHITE
                print(f"    Session Adjustment: {adj_color}{breakdown['session_adjustment']:+d}%{Colors.RESET}")
        
        # Display R:R ratios if available
        rr = sig.get("rr_ratios", {})
        if rr and any(rr.values()):
            print(f"  {Colors.WHITE}Risk:Reward Ratios:{Colors.RESET}")
            if rr.get('tp1_rr'): print(f"    TP1: {Colors.CYAN}1:{rr['tp1_rr']:.1f}{Colors.RESET}")
            if rr.get('tp2_rr'): print(f"    TP2: {Colors.CYAN}1:{rr['tp2_rr']:.1f}{Colors.RESET}")
            if rr.get('tp3_rr'): print(f"    TP3: {Colors.CYAN}1:{rr['tp3_rr']:.1f}{Colors.RESET}")
        
        # Display time projection if available
        if sig.get("time_projection"):
            print(f"  {Colors.WHITE}Time Projection: {Colors.CYAN}{sig['time_projection']}{Colors.RESET}")
        
        if sig.get("analysis"):
            print(f"  {Colors.DIM}Analysis: {sig['analysis']}{Colors.RESET}")
        
        # Display alerts if any
        alerts = sig.get("alerts", [])
        if alerts:
            print(f"  {Colors.YELLOW}Alerts:{Colors.RESET}")
            for alert in alerts:
                print(f"    • {alert}")
        
        # Display key levels
        levels = sig.get("key_levels", {})
        if levels:
            print(f"  {Colors.WHITE}Key Levels:{Colors.RESET}")
            if levels.get('support'): print(f"    Support: {Colors.RED}{levels['support']}{Colors.RESET}")
            if levels.get('resistance'): print(f"    Resistance: {Colors.GREEN}{levels['resistance']}{Colors.RESET}")
        
        # Display guardian status
        guardian = sig.get("guardian", {})
        if guardian:
            print(f"  {Colors.WHITE}Guardian Filters:{Colors.RESET}")
            
            # Anti-Range check
            anti_range = guardian.get('anti_range_pass', False)
            color = Colors.GREEN if anti_range else Colors.RED
            print(f"    Anti-Range: {color}{'PASS' if anti_range else 'FAIL'}{Colors.RESET}")
            
            # Confluence check
            confluence = guardian.get('confluence_pass', False)
            color = Colors.GREEN if confluence else Colors.RED
            print(f"    Confluence: {color}{'PASS' if confluence else 'FAIL'}{Colors.RESET}")
            
            # MaxProtect check
            max_protect = guardian.get('max_protect_pass', False)
            color = Colors.GREEN if max_protect else Colors.RED
            print(f"    MaxProtect: {color}{'PASS' if max_protect else 'FAIL'}{Colors.RESET}")
            
            # Session check (if present)
            if 'session_ok' in guardian:
                session_ok = guardian.get('session_ok', False)
                color = Colors.GREEN if session_ok else Colors.RED
                print(f"    Session: {color}{'PASS' if session_ok else 'FAIL'}{Colors.RESET}")
            
            # Structure check (if present)
            if 'structure_ok' in guardian:
                structure_ok = guardian.get('structure_ok', False)
                color = Colors.GREEN if structure_ok else Colors.RED
                print(f"    Structure: {color}{'PASS' if structure_ok else 'FAIL'}{Colors.RESET}")
            
            # Flow check (if present)
            if 'flow_ok' in guardian:
                flow_ok = guardian.get('flow_ok', False)
                color = Colors.GREEN if flow_ok else Colors.RED
                print(f"    Flow: {color}{'PASS' if flow_ok else 'FAIL'}{Colors.RESET}")
        
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
        
        # Check trading hours
        hours_allowed, hours_reason = is_trading_hours_allowed()
        if not hours_allowed:
            print_trade_decision(symbol, "BLOCKED", f"Trading hours restriction: {hours_reason}")
            log_trade(decision_id, symbol, action, confidence, "", "", "", status="BLOCKED", reason=f"Hours: {hours_reason}")
            continue
        
        # Check if position already open (already managed by auto-refresh)
        if symbol in open_pos:
            print_trade_decision(symbol, "MANAGED", "Position actively managed by auto-refresh system")
            log_trade(decision_id, symbol, action, confidence, "", "", "", status="MANAGED", reason="Auto-refresh active")
            continue
        
        # Open new position
        entry = sig.get("entry")
        sl = sig.get("sl")
        tp = sig.get("tp")
        
        if entry and sl and tp:
            print_trade_decision(symbol, "OPEN", f"High confidence signal ({confidence:.1f}%) - Thanatos approved")
            key_levels = sig.get("key_levels", {})
            # Get ATR from technical data if available
            atr_value = sig.get("atr", None)
            res = open_trade(symbol, action, float(sl), float(tp), key_levels, atr_value)
            
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
    # Validate configuration first
    if not validate_config():
        print_error("Configuration validation failed. Please check enhanced_config_btc_xau.py")
        return
    
    init_logger()
    print_header()
    print_info("Using Thanatos-Guardian-Prime v15.6-TOLERANT Protocol (MaxProtect ACTIVE but TOLERANT)")
    print_info(f"Trading instruments: {', '.join(TRADING_INSTRUMENTS)}")
    
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
    print_info(f"Risk per trade: {RISK_MANAGEMENT_CONFIG['max_risk_percent_per_trade']}%")
    print_info(f"Minimum confidence: {MIN_CONFIDENCE}%")
    print_info(f"Check interval: {MIN_RECHECK}-{MAX_RECHECK} minutes")
    print_warning("Guardian Filters Active: Anti-Range, News Filter, MaxProtect (TOLERANT MODE)")
    
    # Initialize execution speed optimizations
    exec_config = SYSTEM_CONFIG.get('execution_optimization', {})
    if exec_config.get('enabled', True):
        print_info("⚡ Speed optimizations enabled:")
        print_info(f"  - Fast mode: {'ON' if exec_config.get('fast_mode') else 'OFF'}")
        print_info(f"  - Pre-calculated sizes: {'ON' if exec_config.get('pre_calculate_sizes') else 'OFF'}")
        print_info(f"  - Execution timeout: {exec_config.get('trade_execution_timeout', 5)}s")
        print_info(f"  - Slippage tolerance: {exec_config.get('slippage_tolerance', 3)} pips")
        
        # Initial cache population
        print_info("Initializing speed cache...")
        update_precalc_cache(force_update=True)
    
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