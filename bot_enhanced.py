#!/usr/bin/env python3
"""
Enhanced MT5 Multi-Pair Autotrader with Volume-Adaptive Strategy
Using Thanatos-Volume-Adaptive v16.0-VOLVOLT-TRIAD prompt
- Pairs: XAUUSD, BTCUSD (configurable)
- Triple position strategies based on Volume/Volatility ratio
- Independent monitoring per pair
- Sequential analysis with immediate decisions
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
import threading
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
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "78"))

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

# Continuous monitoring control - INDEPENDENT PER PAIR
monitoring_threads = {}  # Dictionary of threads per symbol
stop_monitoring = {}  # Dictionary of stop flags per symbol
last_analysis_signals = {}  # Store latest signals per symbol for continuous monitoring

# Pre-calculated data cache for speed optimization
precalc_cache = {
    'account_info': None,
    'position_sizes': {},
    'spread_info': {},
    'last_update': 0
}

def continuous_position_monitor(symbol):
    """Continuous monitoring thread for a specific pair - checks every 30 seconds for signal reversals"""
    global stop_monitoring, last_analysis_signals
    
    print_info(f"Starting continuous monitoring for {symbol} (30-second intervals)")
    
    while not stop_monitoring.get(symbol, False):
        try:
            # Only monitor if we have a position for THIS symbol
            positions = mt5.positions_get(symbol=symbol)
            if positions and symbol in last_analysis_signals:
                print_separator()
                print_info(f"MONITOR CHECK [{symbol}] - {datetime.now().strftime('%H:%M:%S')}")
                
                # Perform signal reversal check for THIS symbol only
                signal_list = [last_analysis_signals[symbol]] if last_analysis_signals.get(symbol) else []
                if signal_list:
                    auto_refresh_open_trades(signal_list)
                
            # Sleep for 30 seconds
            time.sleep(30)
            
        except Exception as e:
            print_error(f"Error monitoring {symbol}: {e}")
            time.sleep(30)  # Continue monitoring even on error
    
    print_info(f"Monitoring thread stopped for {symbol}")

def start_continuous_monitoring(symbol):
    """Start continuous monitoring thread for a specific symbol if not already running"""
    global monitoring_threads, stop_monitoring
    
    # Check if monitoring already running for this symbol
    if symbol in monitoring_threads and monitoring_threads[symbol].is_alive():
        return  # Already running for this symbol
    
    stop_monitoring[symbol] = False
    monitoring_threads[symbol] = threading.Thread(
        target=continuous_position_monitor, 
        args=(symbol,),
        daemon=True,
        name=f"Monitor-{symbol}"
    )
    monitoring_threads[symbol].start()
    print_success(f"Monitoring started for {symbol} (30-second checks)")

def stop_continuous_monitoring(symbol=None):
    """Stop continuous monitoring thread(s)
    If symbol is provided, stop only that symbol's monitoring
    If no symbol, stop all monitoring threads"""
    global stop_monitoring, monitoring_threads
    
    if symbol:
        # Stop specific symbol monitoring
        if symbol in stop_monitoring:
            stop_monitoring[symbol] = True
            if symbol in monitoring_threads:
                monitoring_threads[symbol].join(timeout=5)
                print_info(f"Monitoring stopped for {symbol}")
    else:
        # Stop all monitoring threads
        for sym in list(stop_monitoring.keys()):
            stop_monitoring[sym] = True
        
        for sym, thread in monitoring_threads.items():
            if thread.is_alive():
                thread.join(timeout=5)
        
        print_info("All monitoring threads stopped")

def analyze_positions_for_reversal(symbol=None):
    """Perform immediate analysis to check for signal reversals
    If symbol provided, check only that symbol
    Otherwise check all positions"""
    
    if symbol:
        # Check specific symbol
        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            return
        
        print_separator()
        print_info(f"SIGNAL REVERSAL CHECK [{symbol}]")
        
        try:
            # Calculate technical indicators
            tech_data = calculate_technical_indicators(symbol)
            if tech_data:
                # Get AI signal
                signal = get_ai_signal(symbol, tech_data)
                if signal:
                    # Update last signal for this symbol
                    global last_analysis_signals
                    last_analysis_signals[symbol] = signal
                    
                    # Check for reversal
                    auto_refresh_open_trades([signal])
        except Exception as e:
            print_error(f"Error analyzing {symbol}: {e}")
    else:
        # Check all positions
        positions = mt5.positions_get()
        if not positions:
            return
        
        print_separator()
        print_info("SIGNAL REVERSAL CHECK [ALL PAIRS]")
        
        # Get fresh signals for all open positions
        symbols_with_positions = {pos.symbol for pos in positions}
        
        for symbol in symbols_with_positions:
            try:
                # Calculate technical indicators
                tech_data = calculate_technical_indicators(symbol)
                if not tech_data:
                    continue
                
                # Get AI signal
                signal = get_ai_signal(symbol, tech_data)
                if signal:
                    # Update last signal for this symbol
                    last_analysis_signals[symbol] = signal
                    
                    # Check for reversal for this symbol
                    auto_refresh_open_trades([signal])
                    
            except Exception as e:
                print_error(f"Error analyzing {symbol}: {e}")

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
    """Calculate technical indicators for all timeframes (D1, H1, M15, M5)"""
    # Get data for all timeframes
    rates_d1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 200)  # Need 200 for EMA200
    rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 200)
    rates_m15 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 200)
    rates_m5 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 200)
    
    if rates_h1 is None or len(rates_h1) < 30:
        return None
    
    df_d1 = pd.DataFrame(rates_d1) if rates_d1 is not None and len(rates_d1) >= 30 else None
    df_h1 = pd.DataFrame(rates_h1)
    df_m15 = pd.DataFrame(rates_m15) if rates_m15 is not None else None
    df_m5 = pd.DataFrame(rates_m5) if rates_m5 is not None else None
    
    # Debug: Print available columns for M5 data
    print_info(f"Available M5 columns for {symbol}: {list(df_m5.columns)}")
    
    current_price = float(df_h1['close'].iloc[-1])
    
    # Helper function to calculate all indicators for a timeframe
    def calculate_timeframe_indicators(df, timeframe_name):
        """Calculate all indicators for a specific timeframe"""
        if df is None or len(df) < 30:
            return None
            
        result = {}
        close_price = float(df['close'].iloc[-1])
        
        # EMAs
        ema20 = df['close'].ewm(span=20, adjust=False).mean().iloc[-1]
        ema50 = df['close'].ewm(span=50, adjust=False).mean().iloc[-1] if len(df) >= 50 else 0
        ema200 = df['close'].ewm(span=200, adjust=False).mean().iloc[-1] if len(df) >= 200 else 0
        
        # Bollinger Bands
        sma20 = df['close'].rolling(window=20).mean()
        std20 = df['close'].rolling(window=20).std()
        bb_upper = (sma20 + (2 * std20)).iloc[-1]
        bb_lower = (sma20 - (2 * std20)).iloc[-1]
        bb_middle = sma20.iloc[-1]
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_value = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
        
        # MACD
        exp1 = df['close'].ewm(span=12, adjust=False).mean()
        exp2 = df['close'].ewm(span=26, adjust=False).mean()
        macd_line = exp1 - exp2
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        macd_histogram = macd_line - signal_line
        
        # ADX
        high = df['high']
        low = df['low']
        close = df['close']
        
        plus_dm = high.diff()
        minus_dm = low.diff().abs()
        tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
        
        atr = tr.rolling(window=14).mean()
        plus_di = 100 * (plus_dm.rolling(window=14).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=14).mean() / atr)
        
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=14).mean()
        adx_value = adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 20.0
        
        # ATR
        atr_value = atr.iloc[-1] if not pd.isna(atr.iloc[-1]) else 0
        
        # Volume
        volume_last30 = df.tail(30)['tick_volume'].values if 'tick_volume' in df.columns else []
        volume_avg = np.mean(volume_last30) if len(volume_last30) > 0 else 0
        volume_current = volume_last30[-1] if len(volume_last30) > 0 else 0
        
        result = {
            'price': close_price,
            'ema20': round(ema20, 5),
            'ema50': round(ema50, 5) if ema50 > 0 else 'N/A',
            'ema200': round(ema200, 5) if ema200 > 0 else 'N/A',
            'bb_upper': round(bb_upper, 5),
            'bb_middle': round(bb_middle, 5),
            'bb_lower': round(bb_lower, 5),
            'rsi': round(rsi_value, 2),
            'macd': round(macd_line.iloc[-1], 5),
            'macd_signal': round(signal_line.iloc[-1], 5),
            'macd_hist': round(macd_histogram.iloc[-1], 5),
            'adx': round(adx_value, 1),
            'atr': round(atr_value, 5),
            'volume_current': int(volume_current),
            'volume_avg': int(volume_avg),
            'price_vs_ema20': 'above' if close_price > ema20 else 'below',
            'price_vs_ema50': 'above' if close_price > ema50 and ema50 > 0 else 'below' if ema50 > 0 else 'N/A',
            'price_vs_ema200': 'above' if close_price > ema200 and ema200 > 0 else 'below' if ema200 > 0 else 'N/A',
            'bb_position': 'above' if close_price > bb_upper else 'below' if close_price < bb_lower else 'inside',
            'rsi_zone': 'overbought' if rsi_value > 70 else 'oversold' if rsi_value < 30 else 'neutral',
            'macd_trend': 'bullish' if macd_line.iloc[-1] > signal_line.iloc[-1] else 'bearish'
        }
        
        return result
    
    # Calculate indicators for all timeframes
    indicators_d1 = calculate_timeframe_indicators(df_d1, 'D1') if df_d1 is not None else None
    indicators_h1 = calculate_timeframe_indicators(df_h1, 'H1')
    indicators_m15 = calculate_timeframe_indicators(df_m15, 'M15') if df_m15 is not None else None
    indicators_m5 = calculate_timeframe_indicators(df_m5, 'M5') if df_m5 is not None else None
    
    # Calculate ADX(14) on H1 (keeping original for compatibility)
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
    
    # Calculate EMAs (20, 50, 200) on last 30 candles
    df_h1_last30 = df_h1.tail(30).copy()
    ema20 = df_h1['close'].ewm(span=20, adjust=False).mean().iloc[-1]
    ema50 = df_h1['close'].ewm(span=50, adjust=False).mean().iloc[-1]
    ema200 = df_h1['close'].ewm(span=200, adjust=False).mean().iloc[-1] if len(df_h1) >= 200 else 0
    
    # Calculate Bollinger Bands (20, 2)
    sma20 = df_h1['close'].rolling(window=20).mean()
    std20 = df_h1['close'].rolling(window=20).std()
    bb_upper = sma20 + (2 * std20)
    bb_lower = sma20 - (2 * std20)
    bb_middle = sma20.iloc[-1]
    bb20_width_pct_h1 = ((bb_upper.iloc[-1] - bb_lower.iloc[-1]) / current_price) * 100
    
    # Calculate RSI(14) on last 30 candles
    def calculate_rsi(df, period=14):
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
    
    rsi14 = calculate_rsi(df_h1_last30)
    
    # Calculate MACD (12, 26, 9)
    exp1 = df_h1['close'].ewm(span=12, adjust=False).mean()
    exp2 = df_h1['close'].ewm(span=26, adjust=False).mean()
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_histogram = macd_line - signal_line
    
    macd_value = macd_line.iloc[-1]
    macd_signal = signal_line.iloc[-1]
    macd_hist = macd_histogram.iloc[-1]
    
    # Volume analysis for last 30 candles
    volume_last30 = df_h1_last30['tick_volume'].values if 'tick_volume' in df_h1_last30.columns else []
    volume_avg = np.mean(volume_last30) if len(volume_last30) > 0 else 0
    volume_current = volume_last30[-1] if len(volume_last30) > 0 else 0
    
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
        "timeframes": {
            "D1": indicators_d1,
            "H1": indicators_h1,
            "M15": indicators_m15,
            "M5": indicators_m5
        },
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
        "ema_levels": {
            "ema20": round(ema20, 5),
            "ema50": round(ema50, 5),
            "ema200": round(ema200, 5) if ema200 > 0 else "N/A",
            "price_vs_ema20": "above" if current_price > ema20 else "below",
            "price_vs_ema50": "above" if current_price > ema50 else "below",
            "price_vs_ema200": "above" if current_price > ema200 and ema200 > 0 else "below" if ema200 > 0 else "N/A"
        },
        "bollinger_bands": {
            "upper": round(bb_upper.iloc[-1], 5),
            "middle": round(bb_middle, 5),
            "lower": round(bb_lower.iloc[-1], 5),
            "width_pct": round(bb20_width_pct_h1, 2),
            "position": "above_upper" if current_price > bb_upper.iloc[-1] else "below_lower" if current_price < bb_lower.iloc[-1] else "inside"
        },
        "momentum": {
            "rsi14": round(rsi14, 2),
            "rsi_zone": "overbought" if rsi14 > 70 else "oversold" if rsi14 < 30 else "neutral",
            "macd": round(macd_value, 5),
            "macd_signal": round(macd_signal, 5),
            "macd_histogram": round(macd_hist, 5),
            "macd_trend": "bullish" if macd_value > macd_signal else "bearish"
        },
        "volume_analysis": {
            "current": int(volume_current),
            "avg_30": int(volume_avg),
            "vs_avg": "above" if volume_current > volume_avg else "below",
            "ratio": round(volume_current / volume_avg, 2) if volume_avg > 0 else 0
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
            print_info(f"DYNAMIC TRAILING STOP UPDATE for {position.symbol} {('BUY' if position.type == mt5.POSITION_TYPE_BUY else 'SELL')}")
            print_info(f"  Profit: ${position.profit:.2f} | Movement: {profit_pips:.1f} pips")
            print_info(f"  Current Price: {current_price:.5f} | Old SL: {current_sl:.5f} | New SL: {new_sl:.5f}")
            print_info(f"  Trail Distance: 10 pips (keeping profit locked)")
            
            if modify_trailing_sl(position.ticket, new_sl, position.tp if position.tp else 0, position.symbol):
                print_success(f"Dynamic trailing stop updated - protecting ${position.profit:.2f} profit")

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
    # Determine which symbols we're checking
    symbols_checking = {sig["symbol"] for sig in signals if "symbol" in sig}
    
    if not symbols_checking:
        return
    
    # Get positions only for the symbols we're checking
    all_positions = []
    for symbol in symbols_checking:
        symbol_positions = mt5.positions_get(symbol=symbol)
        if symbol_positions:
            all_positions.extend(symbol_positions)
    
    if not all_positions:
        print_info(f"No open positions for {', '.join(symbols_checking)}")
        return
    
    print_separator()
    print_info(f"POSITION MONITORING [{', '.join(symbols_checking)}]")
    print_info(f"   Positions to check: {len(all_positions)}")
    print_info(f"   Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    positions_closed = 0
    positions_maintained = 0
    
    for position in all_positions:
        symbol = position.symbol
        current_type = "BUY" if position.type == mt5.POSITION_TYPE_BUY else "SELL"
        position_profit = position.profit
        position_time = datetime.fromtimestamp(position.time).strftime('%Y-%m-%d %H:%M:%S')
        
        # Find matching signal for this symbol
        matching_signal = None
        for signal in signals:
            if signal["symbol"] == symbol and signal["action"] in ["BUY", "SELL"]:
                matching_signal = signal
                break
        
        if not matching_signal:
            print_info(f"  {symbol}: No actionable signal - maintaining current {current_type} position")
            print_info(f"    Position: Ticket #{position.ticket} | Opened: {position_time} | P/L: €{position_profit:.2f}")
            positions_maintained += 1
            continue
        
        new_action = matching_signal["action"]
        confidence = matching_signal.get("confidence", 0)
        
        # ONLY ACTION: Check if direction changed (close trade)
        if current_type != new_action:
            print_separator()
            print_warning(f"SIGNAL REVERSAL DETECTED for {symbol}")
            print_warning(f"   Current Position: {current_type} (Ticket #{position.ticket})")
            print_warning(f"   New Signal: {new_action} (Confidence: {confidence}%)")
            print_warning(f"   Position P/L: €{position_profit:.2f}")
            print_info(f"   Action: Closing position immediately due to direction change")
            
            close_request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": position.ticket,
                "symbol": symbol,
                "volume": position.volume,
                "type": mt5.ORDER_TYPE_SELL if position.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                "magic": MAGIC_NUMBER,
                "comment": f"Signal reversal: {new_action}",
                "type_filling": mt5.ORDER_FILLING_IOC
            }
            
            result = mt5.order_send(close_request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                print_success(f"Successfully closed {symbol} position #{position.ticket}")
                print_success(f"   Reason: Signal reversal from {current_type} to {new_action}")
                print_success(f"   Final P/L: €{position_profit:.2f}")
                positions_closed += 1
                
                log_trade(
                    str(result.deal or position.ticket),
                    symbol,
                    "CLOSE",
                    confidence,
                    "",
                    "",
                    "",
                    status="AUTO_CLOSED",
                    reason=f"Signal reversal: {current_type} -> {new_action}, P/L: €{position_profit:.2f}"
                )
            else:
                error_msg = mt5.last_error() if hasattr(mt5, 'last_error') else 'Unknown error'
                print_error(f"Failed to close {symbol} position #{position.ticket}")
                print_error(f"   Error code: {result.retcode if result else 'No result'}")
                print_error(f"   Error details: {error_msg}")
        else:
            # Same direction - NO ACTION on SL/TP
            print_info(f"  {symbol}: Signal confirmed {current_type} - position maintained")
            print_info(f"    Position: Ticket #{position.ticket} | P/L: €{position_profit:.2f} | Confidence: {confidence}%")
            positions_maintained += 1
    
    # Summary
    print_separator()
    print_info(f"MONITORING SUMMARY:")
    print_info(f"   Positions closed (reversal): {positions_closed}")
    print_info(f"   Positions maintained: {positions_maintained}")
    print_info(f"   Next check in: 30 seconds")

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

def adjust_tp_sl_atr(symbol: str, entry: float, sl: float, tp: float, atr: float = None) -> tuple:
    """Apply strict ATR-adjusted SL/TP rules for BTCUSD and XAUUSD
    
    BTCUSD (TP increased by 100%):
        SELL: SL = Entry + max(40 pips, 1×ATR), TP = Entry - 130 pips
        BUY:  SL = Entry - max(40 pips, 1×ATR), TP = Entry + 130 pips
    
    XAUUSD:
        SELL: SL = Entry + max(70 pips, 1×ATR), TP = Entry - 140 pips
        BUY:  SL = Entry - max(70 pips, 1×ATR), TP = Entry + 140 pips
    """
    
    # Determine if BUY or SELL based on original SL position
    is_buy = sl < entry
    
    # Get ATR value if not provided
    if atr is None or atr == 0:
        # Try to calculate ATR
        import MetaTrader5 as mt5
        import pandas as pd
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
            print_warning("  [ATR] Could not calculate ATR, using fixed values only")
    
    # Apply rules based on instrument
    if 'BTC' in symbol:
        # BTCUSD: 1 pip = 1 point
        pip_value = 1.0
        
        # Fixed values
        sl_pips = 40  # 40 pips minimum
        tp_pips = 130  # INCREASED by 100%: 65 * 2 = 130 pips
        
        # SL uses max(40 pips, 1×ATR)
        sl_distance = max(sl_pips * pip_value, 1.0 * atr)
        tp_distance = tp_pips * pip_value  # TP is fixed at 130 pips (increased by 100%)
        
        if is_buy:
            # BUY: SL below entry, TP above entry
            final_sl = entry - sl_distance
            final_tp = entry + tp_distance
            print_info(f"  [ATR-RULES] {symbol} BUY:")
            print_info(f"    ATR={atr:.2f}, SL=Entry-max(40, {atr:.2f})={final_sl:.2f}")
            print_info(f"    TP=Entry+130={final_tp:.2f} (increased 100%)")
        else:
            # SELL: SL above entry, TP below entry
            final_sl = entry + sl_distance
            final_tp = entry - tp_distance
            print_info(f"  [ATR-RULES] {symbol} SELL:")
            print_info(f"    ATR={atr:.2f}, SL=Entry+max(40, {atr:.2f})={final_sl:.2f}")
            print_info(f"    TP=Entry-130={final_tp:.2f} (increased 100%)")
            
    elif 'XAU' in symbol:
        # XAUUSD: 1 pip = 0.01 for Gold
        pip_value = 0.01
        
        # Fixed values
        sl_pips = 70   # 70 pips minimum
        tp_pips = 140  # 140 pips fixed (no ATR adjustment for TP)
        
        # SL uses max(70 pips, 1×ATR)
        sl_distance = max(sl_pips * pip_value, 1.0 * atr)
        tp_distance = tp_pips * pip_value  # TP is fixed at 140 pips
        
        if is_buy:
            # BUY: SL below entry, TP above entry
            final_sl = entry - sl_distance
            final_tp = entry + tp_distance
            print_info(f"  [ATR-RULES] {symbol} BUY:")
            print_info(f"    ATR={atr:.2f}, SL=Entry-max(0.70, {atr:.2f})={final_sl:.5f}")
            print_info(f"    TP=Entry+1.40={final_tp:.5f}")
        else:
            # SELL: SL above entry, TP below entry
            final_sl = entry + sl_distance
            final_tp = entry - tp_distance
            print_info(f"  [ATR-RULES] {symbol} SELL:")
            print_info(f"    ATR={atr:.2f}, SL=Entry+max(0.70, {atr:.2f})={final_sl:.5f}")
            print_info(f"    TP=Entry-1.40={final_tp:.5f}")
    else:
        # Unknown symbol, use original values
        print_warning(f"  Unknown symbol {symbol}, using original SL/TP")
        final_sl = sl
        final_tp = tp
    
    # Calculate Risk/Reward ratio
    sl_dist = abs(entry - final_sl)
    tp_dist = abs(final_tp - entry)
    rr_ratio = tp_dist / sl_dist if sl_dist > 0 else 0
    print_info(f"  [ATR-RULES] Risk/Reward Ratio: 1:{rr_ratio:.2f}")
    
    return final_sl, final_tp

def open_trade_fast(symbol: str, action: str, sl: float, tp: float):
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
        
        # Get ATR from technical data
        atr = None
        rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)
        if rates_h1 is not None and len(rates_h1) >= 14:
            df_h1 = pd.DataFrame(rates_h1)
            high = df_h1['high']
            low = df_h1['low']
            close = df_h1['close']
            tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
            atr = tr.rolling(window=14).mean().iloc[-1]
        
        # Apply ATR-adjusted SL/TP rules
        adjusted_sl, adjusted_tp = adjust_tp_sl_atr(symbol, price, sl, tp, atr)
        
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

def open_trade(symbol: str, action: str, sl: float, tp: float):
    """Standard trade execution (fallback or when fast mode disabled)"""
    exec_config = SYSTEM_CONFIG.get('execution_optimization', {})
    
    # Use fast execution if enabled
    if exec_config.get('fast_mode', True):
        return open_trade_fast(symbol, action, sl, tp)
    
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
    
    # Get ATR from technical data
    atr = None
    rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)
    if rates_h1 is not None and len(rates_h1) >= 14:
        df_h1 = pd.DataFrame(rates_h1)
        high = df_h1['high']
        low = df_h1['low']
        close = df_h1['close']
        tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean().iloc[-1]
    
    # Apply ATR-adjusted SL/TP rules
    adjusted_sl, adjusted_tp = adjust_tp_sl_atr(symbol, price, sl, tp, atr)
    
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
    Check MaxProtect with ULTRA-TOLERANT rules (20% more tolerant)
    Returns True if MaxProtect passes (trading allowed)
    Now allows:
    - Up to 2 conflicts between timeframes (was 1)
    - Partial alignment (2 out of 3 timeframes)
    - Weak trends counted as neutral
    """
    try:
        # Extract trend directions from technical data
        h1_trend = technical_data.get('mtf_state', {}).get('H1_trend', 'unknown')
        m15_trend = technical_data.get('mtf_state', {}).get('M15_trend', 'unknown')
        m5_setup = technical_data.get('mtf_state', {}).get('M5_setup', 'unknown')
        
        # Convert trend strings to simplified direction with more tolerance
        def simplify_trend(trend, strength_threshold=0.8):
            trend_lower = str(trend).lower()
            # Sideways/weak trends are now considered neutral (more tolerant)
            if 'sideways' in trend_lower or 'weak' in trend_lower or 'neutral' in trend_lower:
                return 'neutral'
            elif 'bullish' in trend_lower or 'up' in trend_lower or 'buy' in trend_lower:
                return 'up'
            elif 'bearish' in trend_lower or 'down' in trend_lower or 'sell' in trend_lower:
                return 'down'
            elif 'breakout' in trend_lower:
                return 'breakout'  # Special case for M5 breakouts
            else:
                return 'neutral'
        
        h1_dir = simplify_trend(h1_trend)
        m15_dir = simplify_trend(m15_trend)
        m5_dir = simplify_trend(m5_setup)
        
        # Count aligned vs conflicting (more tolerant counting)
        aligned = 0
        total_non_neutral = 0
        
        directions = [h1_dir, m15_dir, m5_dir]
        non_neutral_dirs = [d for d in directions if d != 'neutral']
        
        if len(non_neutral_dirs) == 0:
            # All neutral - allow trading
            return True
        
        if len(non_neutral_dirs) == 1:
            # Only one trend - allow trading
            return True
        
        # Count alignment among non-neutral trends
        # Breakouts are considered aligned with the direction they break towards
        if 'breakout' in non_neutral_dirs:
            # Breakouts get special treatment - more tolerant
            return True
        
        # Check if majority are aligned (2 out of 3)
        up_count = non_neutral_dirs.count('up')
        down_count = non_neutral_dirs.count('down')
        
        # ULTRA-TOLERANT: Allow if at least 50% are aligned (was 66%)
        if len(non_neutral_dirs) >= 2:
            # If 2 or more trends exist, allow if majority agrees
            if up_count >= len(non_neutral_dirs) * 0.5 or down_count >= len(non_neutral_dirs) * 0.5:
                return True
        
        # ULTRA-TOLERANT: Allow up to 2 conflicts (was 1)
        conflicts = 0
        if h1_dir != 'neutral' and m15_dir != 'neutral' and h1_dir != m15_dir:
            conflicts += 1
        if h1_dir != 'neutral' and m5_dir != 'neutral' and h1_dir != m5_dir:
            conflicts += 0.5  # M5 conflicts count less (more tolerant)
        if m15_dir != 'neutral' and m5_dir != 'neutral' and m15_dir != m5_dir:
            conflicts += 0.5  # M5 conflicts count less
        
        # ULTRA-TOLERANT: Allow up to 2 weighted conflicts
        if conflicts <= 2:
            return True
        
        # Special case: Strong H1 trend can override others (20% more weight)
        if h1_dir != 'neutral':
            # H1 has 20% more weight in decision
            return True
        
        # Default: still fail if severe conflicts
        return conflicts < 2.5
        
    except Exception as e:
        print_warning(f"MaxProtect check error: {e} - defaulting to PASS (tolerant)")
        return True  # Default to pass on error to be tolerant

def calculate_volume_volatility_ratio(technical_data: dict) -> tuple:
    """Calculate Volume/Volatility ratio for adaptive strategy
    Returns: (ratio, ratio_category)
    """
    # Get current volume and average volume
    volume_current = technical_data.get('volume_analysis', {}).get('current', 0)
    volume_avg = technical_data.get('volume_analysis', {}).get('avg_30', 1)
    
    # Get ATR percentage as volatility measure
    atr_pct = technical_data.get('measures', {}).get('atr_h1_pct', 0.5)
    
    # Calculate volume ratio (current vs average)
    volume_ratio = volume_current / volume_avg if volume_avg > 0 else 1.0
    
    # Calculate Volume/Volatility ratio
    if atr_pct > 0:
        vv_ratio = volume_ratio / atr_pct
    else:
        vv_ratio = volume_ratio / 0.5  # Default volatility if ATR is 0
    
    # Determine category
    if vv_ratio < 0.5:
        category = "low"  # Calm market
    elif vv_ratio <= 1.5:
        category = "medium"  # Balanced market
    else:
        category = "high"  # Impulsive market
    
    return vv_ratio, category

def deepseek_analyze(symbol: str, technical_data: dict, account_info) -> dict:
    """Use the Thanatos-Guardian-Prime prompt with ratio-based adaptation"""
    headers = {"Authorization": f"Bearer {LLM_KEY}", "Content-Type":"application/json"}
    
    # Check news
    blocked, reason = is_blocked_now(symbol)
    red_news_window = blocked
    
    # UK close check removed - no longer blocking trades after UK close
    now = datetime.now()
    uk_close_block = False  # Disabled UK close protection
    
    # MaxProtect reactivated with ULTRA-tolerant rules (+20%)
    maxprotect_pass = check_tolerant_maxprotect(technical_data, {'allow_conflicts': 2, 'h1_weight': 1.2})
    
    # Determine session weight for adaptive confidence
    session_weight = 0
    if technical_data['sessions']['active'] == "New York" and technical_data['sessions']['ny_open_boost']:
        session_weight = 3
    elif technical_data['sessions']['active'] == "London":
        session_weight = 2
    elif technical_data['sessions']['active'] == "Asian":
        session_weight = -2
    
    # Calculate Volume/Volatility ratio for adaptive strategy
    vv_ratio, ratio_category = calculate_volume_volatility_ratio(technical_data)
    print_info(f"Volume/Volatility Ratio: {vv_ratio:.2f} ({ratio_category.upper()}) - Applying {ratio_category} market rules")
    
    # Get instrument-specific characteristics
    instrument_config = get_instrument_config(symbol)
    instrument_type = instrument_config.get('type', 'unknown')
    volatility_profile = instrument_config.get('volatility', 'medium')
    
    # Build market context string
    market_context = f"""
SYMBOL: {symbol}
TIME: {technical_data['timestamp_cet']} CET
PRICE: {technical_data['price']}
SESSION: {technical_data['sessions']['active']}
NEWS: {'BLOCKED' if red_news_window else 'CLEAR'}
EQUITY: ${account_info.equity:.2f}
VOLUME/VOLATILITY RATIO: {vv_ratio:.2f} ({ratio_category.upper()})
ATR%: {technical_data['measures']['atr_h1_pct']:.2f}%
VOLUME: Current={technical_data['volume_analysis']['current']} | Avg={technical_data['volume_analysis']['avg_30']}"""

    
    # Build the prompt with VOLVOLT-TRIAD strategy
    # Calculate volume metrics for the prompt
    volume_ma50 = technical_data['volume_analysis'].get('avg_30', 0) * 1.67  # Approximation of MA50
    volume_ma100 = technical_data['volume_analysis'].get('avg_30', 0) * 3.33  # Approximation of MA100
    volume_ma200 = technical_data['volume_analysis'].get('avg_30', 0) * 6.67  # Approximation of MA200
    current_volume = technical_data['volume_analysis'].get('current', 0)
    volume_vs_ma50 = (current_volume / volume_ma50 * 100) if volume_ma50 > 0 else 0
    
    # Determine regime based on VV ratio
    if vv_ratio < 0.7:
        regime = "Ranging"
        profile = "Low Volume/High Vol"
    elif vv_ratio > 1.5:
        regime = "Breakout"
        profile = "High Volume/Low Vol"
    else:
        regime = "Trending"
        profile = "Balanced Volume/Vol"
    
    prompt = f"""meta:
  version: "16.0-VOLVOLT-TRIAD"
  codename: "Thanatos-Volume-Adaptive"
  input_requirements: "VALID (D1/H1/M15/M5 avec 50+ bougies, heure CET)"
  response_rules: "STRICT_YAML_ONLY | QUADRUPLE_PASS_REQUIRED"
  adaptive_weighting: "Poids volume-volatilite + ajustement horaire session"
  min_confidence_threshold: "78%"

volume_volatility_analysis:
  vv_ratio: "{vv_ratio:.2f}"
  regime: "{regime}"
  profile: "{profile}"
  adaptive_scaling: "Active (3 profils detectes)"

triad_position_strategy:
  position_1:  # Standard (Volume equilibre)
    type: "CORE"
    activation_condition: "VV Ratio 0.8-1.2 + Alignement MTF"
    risk_ratio: "1:2.1"
    volume_requirement: "> MA50 +15%"
  
  position_2:  # Agressive (Faible volume/Haute volatilite)
    type: "MOMENTUM"
    activation_condition: "VV Ratio <0.7 + Cassure cle"
    risk_ratio: "1:3.5"
    volume_requirement: "Spike > MA200"
  
  position_3:  # Conservative (Haut volume/Faible volatilite)
    type: "FLOW"
    activation_condition: "VV Ratio >1.5 + Support/Resistance"
    risk_ratio: "1:1.8"
    volume_requirement: "Volume stable > MA100"

# CURRENT MARKET STATE
VOLUME_VOLATILITY_RATIO: {vv_ratio:.2f}
REGIME: {regime}
PROFILE: {profile}
VOLUME_VS_MA50: {volume_vs_ma50:.1f}%
SESSION: {technical_data['sessions']['active']}
NEWS_STATUS: {'BLOCKED' if red_news_window else 'CLEAR'}

# MULTI-TIMEFRAME TECHNICAL INDICATORS (30 CANDLES)

""" + (f"""
### D1 (DAILY) TIMEFRAME
EMA: 20={technical_data['timeframes']['D1']['ema20'] if technical_data['timeframes']['D1'] else 'N/A'} | 50={technical_data['timeframes']['D1']['ema50'] if technical_data['timeframes']['D1'] else 'N/A'} | 200={technical_data['timeframes']['D1']['ema200'] if technical_data['timeframes']['D1'] else 'N/A'}
Price vs EMAs: {technical_data['timeframes']['D1']['price_vs_ema20'] if technical_data['timeframes']['D1'] else 'N/A'} EMA20 | {technical_data['timeframes']['D1']['price_vs_ema50'] if technical_data['timeframes']['D1'] else 'N/A'} EMA50 | {technical_data['timeframes']['D1']['price_vs_ema200'] if technical_data['timeframes']['D1'] else 'N/A'} EMA200
Bollinger: Upper={technical_data['timeframes']['D1']['bb_upper'] if technical_data['timeframes']['D1'] else 'N/A'} | Middle={technical_data['timeframes']['D1']['bb_middle'] if technical_data['timeframes']['D1'] else 'N/A'} | Lower={technical_data['timeframes']['D1']['bb_lower'] if technical_data['timeframes']['D1'] else 'N/A'} | Position={technical_data['timeframes']['D1']['bb_position'] if technical_data['timeframes']['D1'] else 'N/A'}
RSI(14): {technical_data['timeframes']['D1']['rsi'] if technical_data['timeframes']['D1'] else 'N/A'} ({technical_data['timeframes']['D1']['rsi_zone'] if technical_data['timeframes']['D1'] else 'N/A'})
MACD: {technical_data['timeframes']['D1']['macd'] if technical_data['timeframes']['D1'] else 'N/A'} | Signal={technical_data['timeframes']['D1']['macd_signal'] if technical_data['timeframes']['D1'] else 'N/A'} | Trend={technical_data['timeframes']['D1']['macd_trend'] if technical_data['timeframes']['D1'] else 'N/A'}
ADX: {technical_data['timeframes']['D1']['adx'] if technical_data['timeframes']['D1'] else 'N/A'} | ATR: {technical_data['timeframes']['D1']['atr'] if technical_data['timeframes']['D1'] else 'N/A'}
Volume: Current={technical_data['timeframes']['D1']['volume_current'] if technical_data['timeframes']['D1'] else 'N/A'} | Avg={technical_data['timeframes']['D1']['volume_avg'] if technical_data['timeframes']['D1'] else 'N/A'}
""" if technical_data['timeframes']['D1'] else "### D1 (DAILY) TIMEFRAME\nNo data available\n") + f"""
### H1 (HOURLY) TIMEFRAME
EMA: 20={technical_data['timeframes']['H1']['ema20']} | 50={technical_data['timeframes']['H1']['ema50']} | 200={technical_data['timeframes']['H1']['ema200']}
Price vs EMAs: {technical_data['timeframes']['H1']['price_vs_ema20']} EMA20 | {technical_data['timeframes']['H1']['price_vs_ema50']} EMA50 | {technical_data['timeframes']['H1']['price_vs_ema200']} EMA200
Bollinger: Upper={technical_data['timeframes']['H1']['bb_upper']} | Middle={technical_data['timeframes']['H1']['bb_middle']} | Lower={technical_data['timeframes']['H1']['bb_lower']} | Position={technical_data['timeframes']['H1']['bb_position']}
RSI(14): {technical_data['timeframes']['H1']['rsi']} ({technical_data['timeframes']['H1']['rsi_zone']})
MACD: {technical_data['timeframes']['H1']['macd']} | Signal={technical_data['timeframes']['H1']['macd_signal']} | Trend={technical_data['timeframes']['H1']['macd_trend']}
ADX: {technical_data['timeframes']['H1']['adx']} | ATR: {technical_data['timeframes']['H1']['atr']}
Volume: Current={technical_data['timeframes']['H1']['volume_current']} | Avg={technical_data['timeframes']['H1']['volume_avg']}

""" + (f"""### M15 (15-MINUTE) TIMEFRAME
EMA: 20={technical_data['timeframes']['M15']['ema20'] if technical_data['timeframes']['M15'] else 'N/A'} | 50={technical_data['timeframes']['M15']['ema50'] if technical_data['timeframes']['M15'] else 'N/A'} | 200={technical_data['timeframes']['M15']['ema200'] if technical_data['timeframes']['M15'] else 'N/A'}
Price vs EMAs: {technical_data['timeframes']['M15']['price_vs_ema20'] if technical_data['timeframes']['M15'] else 'N/A'} EMA20 | {technical_data['timeframes']['M15']['price_vs_ema50'] if technical_data['timeframes']['M15'] else 'N/A'} EMA50 | {technical_data['timeframes']['M15']['price_vs_ema200'] if technical_data['timeframes']['M15'] else 'N/A'} EMA200
Bollinger: Upper={technical_data['timeframes']['M15']['bb_upper'] if technical_data['timeframes']['M15'] else 'N/A'} | Middle={technical_data['timeframes']['M15']['bb_middle'] if technical_data['timeframes']['M15'] else 'N/A'} | Lower={technical_data['timeframes']['M15']['bb_lower'] if technical_data['timeframes']['M15'] else 'N/A'} | Position={technical_data['timeframes']['M15']['bb_position'] if technical_data['timeframes']['M15'] else 'N/A'}
RSI(14): {technical_data['timeframes']['M15']['rsi'] if technical_data['timeframes']['M15'] else 'N/A'} ({technical_data['timeframes']['M15']['rsi_zone'] if technical_data['timeframes']['M15'] else 'N/A'})
MACD: {technical_data['timeframes']['M15']['macd'] if technical_data['timeframes']['M15'] else 'N/A'} | Signal={technical_data['timeframes']['M15']['macd_signal'] if technical_data['timeframes']['M15'] else 'N/A'} | Trend={technical_data['timeframes']['M15']['macd_trend'] if technical_data['timeframes']['M15'] else 'N/A'}
ADX: {technical_data['timeframes']['M15']['adx'] if technical_data['timeframes']['M15'] else 'N/A'} | ATR: {technical_data['timeframes']['M15']['atr'] if technical_data['timeframes']['M15'] else 'N/A'}
Volume: Current={technical_data['timeframes']['M15']['volume_current'] if technical_data['timeframes']['M15'] else 'N/A'} | Avg={technical_data['timeframes']['M15']['volume_avg'] if technical_data['timeframes']['M15'] else 'N/A'}

""" if technical_data['timeframes']['M15'] else "### M15 (15-MINUTE) TIMEFRAME\nNo data available\n\n") + (f"""### M5 (5-MINUTE) TIMEFRAME
EMA: 20={technical_data['timeframes']['M5']['ema20'] if technical_data['timeframes']['M5'] else 'N/A'} | 50={technical_data['timeframes']['M5']['ema50'] if technical_data['timeframes']['M5'] else 'N/A'} | 200={technical_data['timeframes']['M5']['ema200'] if technical_data['timeframes']['M5'] else 'N/A'}
Price vs EMAs: {technical_data['timeframes']['M5']['price_vs_ema20'] if technical_data['timeframes']['M5'] else 'N/A'} EMA20 | {technical_data['timeframes']['M5']['price_vs_ema50'] if technical_data['timeframes']['M5'] else 'N/A'} EMA50 | {technical_data['timeframes']['M5']['price_vs_ema200'] if technical_data['timeframes']['M5'] else 'N/A'} EMA200
Bollinger: Upper={technical_data['timeframes']['M5']['bb_upper'] if technical_data['timeframes']['M5'] else 'N/A'} | Middle={technical_data['timeframes']['M5']['bb_middle'] if technical_data['timeframes']['M5'] else 'N/A'} | Lower={technical_data['timeframes']['M5']['bb_lower'] if technical_data['timeframes']['M5'] else 'N/A'} | Position={technical_data['timeframes']['M5']['bb_position'] if technical_data['timeframes']['M5'] else 'N/A'}
RSI(14): {technical_data['timeframes']['M5']['rsi'] if technical_data['timeframes']['M5'] else 'N/A'} ({technical_data['timeframes']['M5']['rsi_zone'] if technical_data['timeframes']['M5'] else 'N/A'})
MACD: {technical_data['timeframes']['M5']['macd'] if technical_data['timeframes']['M5'] else 'N/A'} | Signal={technical_data['timeframes']['M5']['macd_signal'] if technical_data['timeframes']['M5'] else 'N/A'} | Trend={technical_data['timeframes']['M5']['macd_trend'] if technical_data['timeframes']['M5'] else 'N/A'}
ADX: {technical_data['timeframes']['M5']['adx'] if technical_data['timeframes']['M5'] else 'N/A'} | ATR: {technical_data['timeframes']['M5']['atr'] if technical_data['timeframes']['M5'] else 'N/A'}
Volume: Current={technical_data['timeframes']['M5']['volume_current'] if technical_data['timeframes']['M5'] else 'N/A'} | Avg={technical_data['timeframes']['M5']['volume_avg'] if technical_data['timeframes']['M5'] else 'N/A'}
""" if technical_data['timeframes']['M5'] else "### M5 (5-MINUTE) TIMEFRAME\nNo data available") + f"""

# RESPOND IN STRICT YAML FORMAT (NO MARKDOWN, NO CODE FENCES):

visual_signal:
  triple_check_status: "VALIDE 4x"
  action: "BUY"  # "BUY" | "SELL" | "NO_TRADE"
  confidence:
    value: 85.7
    level: "high"
    breakdown:
      quantum: 86
      tactical: 84
      psychological: 87
      volume_adaptive: 2.7
    adaptive_note: "VV Ratio favorable + Session {technical_data['sessions']['active']}"
  selected_position: "POSITION_2"  # POSITION_1 | POSITION_2 | POSITION_3
  alerts: ["Volume spike confirme: {volume_vs_ma50:.0f}% MA50"]

guardian_filters:
  volume_volatility_check:
    vv_ok: "Ratio {vv_ratio:.2f} ({regime})"
    regime_ok: "{regime} coherent"
    divergence_ok: "Pas de divergence volume/prix"
  hard_safety: "{'BLOCKED by news' if red_news_window else 'All clear'}"
  soft_safety: ["Volatility {technical_data['measures']['atr_h1_pct']:.1f}%", "DXY stable"]

execution_plan:
  POSITION_1:  # Standard
    ENTRY: {technical_data['price']}
    SL: 0
    TP1: 0
    TP2: 0
    TIME_PROJ: "2h45m"
  
  POSITION_2:  # Momentum (SELECTIONNEE)
    ENTRY: {technical_data['price']}
    SL: 0
    TP1: 0
    TP2: 0
    TP3: 0
    TIME_PROJ: "1h15m"
  
  POSITION_3:  # Conservative
    ENTRY: {technical_data['price']}
    SL: 0
    TP1: 0
    TP2: 0
    TIME_PROJ: "4h30m"

pair_profiles:
  {symbol}:
    volume_signature: "Session {technical_data['sessions']['active']} active"
    optimal_vv_range: "0.9-1.6"
    kill_zones: "Eviter 08:00-09:30 CET"

max_protect_rule:
  volume_filters: "Rejeter si volume < MA50 ou divergence volume/prix >2%"
  status: "Volume coherent avec mouvement"

response_template: |
  # VOLUME-VOLATILITY TRIAD STRATEGY
  DECISION: BUY | CONF: 85.7% | SELECTED: POSITION_2 (MOMENTUM)
  VV RATIO: {vv_ratio:.2f} ({regime} regime) | VOLUME: {volume_vs_ma50:.0f}% MA50
  ENTRY: {{ENTRY}} | SL: {{SL}} | TP1: {{TP1}} (3.5R) | TP2: {{TP2}} (6.8R)
  TIME PROJECTION: 1h15m
  BREAKOUT TRIGGER: Surpasser {{KEY_LEVEL}} avec volume > MA100
  
  # STRATEGIES ALTERNATIVES
  ALTERNATIVE_1 (CORE): SL {{ALT1_SL}} | TP1 {{ALT1_TP1}} (Plus conservative)
  ALTERNATIVE_2 (FLOW): SL {{ALT2_SL}} | TP1 {{ALT2_TP1}} (Volume stable)
  
  # CONTEXTE VOLUMETRIQUE
  VOLUME_SCORE: 87% | VOLATILITY_COMPRESSION: 92%
  SESSION_BOOST: {technical_data['sessions']['active']} (+{session_weight}%) + VV Ratio (+2.7%)

protocol_notes:
  - "Selection automatique position basee sur VV Ratio + structure marche"
  - "Position Momentum: declenchee sur cassure avec volume > MA200"
  - "Position Core: defaut si conditions standards remplies"
  - "Position Flow: activee en faible volatilite + volume stable"
  - "Annuler trade si divergence volume/prix >2%"

optimization_data:
  key_levels:
    support: 0
    resistance: 0
  volume_triggers:
    momentum: "Volume > MA200 + spread < 0.8 pips"
    conservative: "Volume > MA100 + spread < 1.2 pips"

market_context: |
{market_context}
"""
    
    payload = {
        "model": LLM_MODEL,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": f"You are Thanatos-Volume-Adaptive v16.0-VOLVOLT-TRIAD. Current VV Ratio: {vv_ratio:.2f} ({regime}). Volume vs MA50: {volume_vs_ma50:.0f}%. Select optimal position strategy (POSITION_1/2/3) based on market regime. POSITION_1 for balanced markets (VV 0.8-1.2), POSITION_2 for momentum/breakouts (VV <0.7), POSITION_3 for flow trades (VV >1.5). Return ONLY valid YAML, no markdown. Quadruple validation required. Min confidence 78%."},
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
    
    print_info(f"Requesting VOLVOLT-TRIAD analysis (VV Ratio: {vv_ratio:.2f}, Regime: {regime})...")
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
    
    # Strip markdown code blocks more robustly
    # Remove all markdown code block delimiters
    import re
    
    # First, try to extract content between code blocks if they exist
    code_block_pattern = r'```(?:yaml|yml|json)?\s*\n(.*?)\n```'
    match = re.search(code_block_pattern, content, re.DOTALL)
    if match:
        content = match.group(1)
    else:
        # If no matched code block, remove any standalone backticks
        content = re.sub(r'```(?:yaml|yml|json)?', '', content)
        content = re.sub(r'```', '', content)
    
    # Clean up any remaining backticks that might cause issues
    content = content.replace('`', '')
    
    # Remove any leading/trailing whitespace
    content = content.strip()
    
    try:
        parsed = yaml.safe_load(content)
        
        # Debug: log successful parsing
        if parsed:
            print_info("Successfully parsed AI response")
        
        # Handle VOLVOLT-TRIAD format
        if 'visual_signal' in parsed:
            # Extract data from VOLVOLT-TRIAD format
            visual_signal = parsed.get('visual_signal', {})
            execution_plan = parsed.get('execution_plan', {})
            guardian_filters = parsed.get('guardian_filters', {})
            max_protect = parsed.get('max_protect_rule', {})
            optimization = parsed.get('optimization_data', {})
            
            # Determine which position was selected
            selected_position = visual_signal.get('selected_position', 'POSITION_1')
            
            # Get the selected position's execution plan
            selected_plan = {}
            if selected_position in execution_plan:
                selected_plan = execution_plan[selected_position]
            elif 'POSITION_2' in execution_plan:  # Default to POSITION_2 if selection unclear
                selected_plan = execution_plan['POSITION_2']
                selected_position = 'POSITION_2'
            elif 'POSITION_1' in execution_plan:
                selected_plan = execution_plan['POSITION_1']
                selected_position = 'POSITION_1'
            
            # Parse confidence value (handle both float and string)
            confidence_value = visual_signal.get('confidence', {}).get('value', 0)
            if isinstance(confidence_value, str):
                confidence_value = float(confidence_value.replace('%', '').strip())
            elif not isinstance(confidence_value, (int, float)):
                confidence_value = 0
            
            # Build response in expected format
            converted_response = {
                "action": visual_signal.get('action', 'NO_TRADE'),
                "confidence": float(confidence_value) if confidence_value else 0,
                "confidence_breakdown": {
                    k: float(v.replace('%', '').strip()) if isinstance(v, str) else float(v) if v else 0
                    for k, v in visual_signal.get('confidence', {}).get('breakdown', {}).items()
                },
                "selected_position": selected_position,
                "entry": selected_plan.get('ENTRY') or execution_plan.get('entry'),
                "sl": selected_plan.get('SL') or execution_plan.get('sl'),
                "tp1": selected_plan.get('TP1') or execution_plan.get('tp1'),
                "tp2": selected_plan.get('TP2') or execution_plan.get('tp2'),
                "tp3": selected_plan.get('TP3') or execution_plan.get('tp3'),
                "rr_ratios": execution_plan.get('rr_ratios', {}),
                "time_projection": execution_plan.get('time_projection', ''),
                "analysis": parsed.get('analysis', ''),
                "guardian_status": {
                    "anti_range_pass": 'VALIDÉ' in visual_signal.get('triple_check_status', ''),
                    "confluence_pass": 'alignement' in str(guardian_filters.get('mandatory_confluence', {}).get('structure_ok', '')).lower(),
                    "max_protect_pass": 'tolerant' in max_protect.get('status', '').lower() or 'pass' in max_protect.get('status', '').lower() or 'accept' in max_protect.get('status', '').lower(),
                    "session_ok": '✅' in str(guardian_filters.get('mandatory_confluence', {}).get('session_ok', '')),
                    "structure_ok": '✅' in str(guardian_filters.get('mandatory_confluence', {}).get('structure_ok', '')),
                    "flow_ok": '✅' in str(guardian_filters.get('mandatory_confluence', {}).get('flow_ok', ''))
                },
                "alerts": visual_signal.get('alerts', []),
                "key_levels": {
                    k: float(v) if isinstance(v, str) and v.replace('.', '').replace('-', '').isdigit() else v
                    for k, v in optimization.get('key_levels', {}).items()
                },
                "triple_check": visual_signal.get('triple_check_status', '⛔️ NON VALIDÉ'),
                "adaptive_note": visual_signal.get('confidence', {}).get('adaptive_note', ''),
                "response_template": parsed.get('response_template', '')
            }
            
            # Log the prompt and analysis
            log_analysis_prompt(symbol, prompt, checked_rules, parsed)
            
            return converted_response
        # Handle other formats for backward compatibility
        elif 'decision' in parsed or 'regime' in parsed:
            # Simple format conversion
            confidence_value = parsed.get('confidence', {}).get('value', 0) if isinstance(parsed.get('confidence'), dict) else parsed.get('confidence', 0)
            
            converted_response = {
                "action": parsed.get('decision', parsed.get('action', 'NO_TRADE')),
                "confidence": float(confidence_value) if confidence_value else 0,
                "confidence_breakdown": parsed.get('confidence', {}).get('breakdown', {}) if isinstance(parsed.get('confidence'), dict) else {},
                "entry": parsed.get('entry'),
                "sl": parsed.get('sl'),
                "tp1": parsed.get('tp1'),
                "tp2": parsed.get('tp2'),
                "tp3": parsed.get('tp3'),
                "rr_ratios": parsed.get('rr_ratios', {}),
                "time_projection": parsed.get('time_projection', ''),
                "analysis": parsed.get('analysis', ''),
                "guardian_status": {},
                "alerts": parsed.get('alerts', []),
                "key_levels": parsed.get('key_levels', {})
            }
            
            # Log the prompt and analysis
            log_analysis_prompt(symbol, prompt, checked_rules, parsed)
            
            return converted_response
        else:
            # Old format, use as-is
            log_analysis_prompt(symbol, prompt, checked_rules, parsed)
            return parsed
            
    except yaml.YAMLError as e:
        print_error(f"YAML parsing error: {e}")
        print_error(f"Content preview (first 200 chars): {content[:200]}")
        # Try to salvage what we can from the response
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

def analyze_or_monitor_pair(symbol: str, account, blocked_pairs: dict) -> bool:
    """Analyze pair if no position, or monitor if position exists
    Returns True if position was opened, False otherwise"""
    
    # Check if position exists for this pair
    positions = mt5.positions_get(symbol=symbol)
    
    if positions and len(positions) > 0:
        # POSITION EXISTS - MONITOR WITH FRESH ANALYSIS
        position = positions[0]  # Should only be 1 position per pair
        current_type = "BUY" if position.type == mt5.POSITION_TYPE_BUY else "SELL"
        
        print_separator()
        print_info(f"[{symbol}] MONITORING EXISTING POSITION")
        print_info(f"  Ticket: #{position.ticket} | Type: {current_type}")
        print_info(f"  P/L: ${position.profit:.2f} | Open: {datetime.fromtimestamp(position.time).strftime('%H:%M:%S')}")
        
        # Check for SL elevation (breakeven + buffer)
        manage_position_sl_elevation()
        
        # Check for trailing stop
        manage_trailing_stops()
        
        # NEW: Get fresh analysis from DeepSeek to check for direction change
        print_info(f"  Getting fresh market analysis for signal reversal check...")
        
        try:
            # Calculate current technical indicators
            tech_data = calculate_technical_indicators(symbol)
            if tech_data:
                # Get fresh AI analysis
                analysis = deepseek_analyze(symbol, tech_data, account)
                
                # Create fresh signal
                fresh_signal = {
                    "symbol": symbol,
                    "action": analysis.get("action", "NO_TRADE"),
                    "confidence": float(analysis.get("confidence", 0))
                }
                
                # Store the fresh signal
                last_analysis_signals[symbol] = fresh_signal
                
                # Check if direction has changed
                new_action = fresh_signal["action"]
                
                if new_action in ["BUY", "SELL"] and new_action != current_type:
                    # SIGNAL REVERSAL DETECTED!
                    print_separator()
                    print_warning(f"⚠️ SIGNAL REVERSAL DETECTED for {symbol}!")
                    print_warning(f"  Current position: {current_type}")
                    print_warning(f"  New signal: {new_action} (Confidence: {fresh_signal['confidence']:.1f}%)")
                    print_warning(f"  Current P/L: ${position.profit:.2f}")
                    
                    if fresh_signal['confidence'] >= MIN_CONFIDENCE:
                        print_info("  Closing position due to signal reversal...")
                        
                        # Close the position
                        close_request = {
                            "action": mt5.TRADE_ACTION_DEAL,
                            "position": position.ticket,
                            "symbol": symbol,
                            "volume": position.volume,
                            "type": mt5.ORDER_TYPE_SELL if position.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                            "magic": MAGIC_NUMBER,
                            "comment": f"Signal reversal to {new_action}",
                            "type_filling": mt5.ORDER_FILLING_IOC
                        }
                        
                        result = mt5.order_send(close_request)
                        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                            print_success(f"Position closed successfully due to signal reversal")
                            print_info(f"  Final P/L: ${position.profit:.2f}")
                            
                            # Stop monitoring for this symbol
                            stop_continuous_monitoring(symbol)
                            
                            # Log the closure
                            log_trade(
                                str(result.deal or position.ticket),
                                symbol,
                                "CLOSE",
                                fresh_signal['confidence'],
                                "",
                                "",
                                "",
                                status="REVERSED",
                                reason=f"Signal changed from {current_type} to {new_action}"
                            )
                        else:
                            print_error(f"Failed to close position: {result.retcode if result else 'Unknown error'}")
                    else:
                        print_info(f"  New signal confidence too low ({fresh_signal['confidence']:.1f}% < {MIN_CONFIDENCE}%), maintaining position")
                else:
                    print_info(f"  Signal still {current_type} - Position maintained")
                    
        except Exception as e:
            print_error(f"Error getting fresh analysis: {e}")
        
        return False  # No new position opened
        
    else:
        # NO POSITION - ANALYZE AND POTENTIALLY OPEN
        print_separator()
        print_info(f"[{symbol}] ANALYZING FOR NEW POSITION")
        
        # Check if blocked by news
        if symbol in blocked_pairs:
            print_warning(f"  {symbol} blocked: {blocked_pairs[symbol]}")
            return False
        
        # Check trading hours
        hours_allowed, hours_reason = is_trading_hours_allowed()
        if not hours_allowed:
            print_warning(f"  Trading hours blocked: {hours_reason}")
            return False
        
        try:
            # Calculate technical indicators
            tech_data = calculate_technical_indicators(symbol)
            if not tech_data:
                print_error(f"  Failed to calculate indicators for {symbol}")
                return False
            
            # Display market data
            print_market_data(symbol, tech_data['price'], {
                "high": tech_data['measures']['range_high_h1'],
                "low": tech_data['measures']['range_low_h1'],
                "volume": tech_data['measures']['current_volume']
            })
            
            # Get AI analysis
            analysis = deepseek_analyze(symbol, tech_data, account)
            
            # Create signal
            signal = {
                "symbol": symbol,
                "action": analysis.get("action", "NO_TRADE"),
                "confidence": float(analysis.get("confidence", 0)),
                "confidence_breakdown": analysis.get("confidence_breakdown", {}),
                "entry": analysis.get("entry"),
                "sl": analysis.get("sl"),
                "tp": analysis.get("tp1"),
                "selected_position": analysis.get("selected_position", "POSITION_1")
            }
            
            # Store signal for monitoring
            last_analysis_signals[symbol] = signal
            
            # Display AI analysis
            print_ai_analysis(
                symbol, signal["action"], signal["confidence"],
                signal.get("entry"), signal.get("sl"), signal.get("tp")
            )
            
            # Check if we should open position
            if signal["confidence"] >= MIN_CONFIDENCE and signal["action"] in ["BUY", "SELL"]:
                entry = signal.get("entry")
                sl = signal.get("sl")
                tp = signal.get("tp")
                
                if entry and sl and tp:
                    print_trade_decision(symbol, "OPEN", f"Signal {signal['action']} ({signal['confidence']:.1f}%)")
                    res = open_trade(symbol, signal["action"], float(sl), float(tp))
                    
                    if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                        print_success(f"Position opened for {symbol}")
                        # Start monitoring for this symbol
                        start_continuous_monitoring(symbol)
                        return True  # Position opened
                    else:
                        print_error(f"Failed to open position: {getattr(res,'retcode',None)}")
            else:
                print_info(f"  No trade signal or low confidence ({signal.get('confidence', 0):.1f}%)")
                
        except Exception as e:
            print_error(f"Error analyzing {symbol}: {e}")
        
        return False  # No position opened

def cycle_once():
    """New continuous cycle: analyze or monitor each pair sequentially"""
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
    
    # Display current positions summary
    open_pos = open_positions_map()
    print_separator()
    print_info("POSITION STATUS")
    if open_pos:
        for sym, pos_info in open_pos.items():
            print(f"  • {sym}: {pos_info}")
    else:
        print_info("  No positions open")
    
    # Check news blocks for all pairs
    blocked_pairs = {}
    for symbol in PAIRS:
        blocked, reason = is_blocked_now(symbol)
        if blocked:
            blocked_pairs[symbol] = reason
    
    if blocked_pairs:
        print_warning("NEWS BLOCKS:")
        for sym, reason in blocked_pairs.items():
            print(f"  • {sym}: {reason}")
    
    # SEQUENTIAL PROCESSING: ALWAYS XAUUSD FIRST, THEN BTCUSD
    print_separator()
    print_info("SEQUENTIAL PAIR PROCESSING")
    
    # 1. Process XAUUSD
    print_info("═══ [1/2] XAUUSD ═══")
    analyze_or_monitor_pair("XAUUSD", account, blocked_pairs)
    
    # 2. Process BTCUSD  
    print_info("═══ [2/2] BTCUSD ═══")
    analyze_or_monitor_pair("BTCUSD", account, blocked_pairs)
    
    # Summary
    print_separator()
    print_info("CYCLE COMPLETE")
    open_pos_after = open_positions_map()
    print_info(f"  Active positions: {len(open_pos_after)}/2")
    if open_pos_after:
        for sym in open_pos_after:
            print_info(f"    • {sym}: Position active")
    
    # End of new cycle_once - return here
    return
    
    # OLD CODE BELOW (now unreachable)
    blocked_pairs = {}
    for symbol in PAIRS:
        blocked, reason = is_blocked_now(symbol)
        if blocked:
            blocked_pairs[symbol] = reason
    print_news_status(blocked_pairs)
    
    # Analyze each pair SEQUENTIALLY and make decision after each analysis
    print_separator()
    print_info("PERFORMING SEQUENTIAL MARKET ANALYSIS")
    print_info("   (Analyzing one pair at a time, decision after each)")
    signals = []
    
    for symbol in PAIRS:
        print_separator()
        print_info(f"Analyzing {symbol}...")
        
        # Check if we can still open positions before analyzing
        open_pos = open_positions_map()  # Refresh position map
        current_positions = len(open_pos)
        
        # Skip analysis if max positions reached AND this symbol already has position
        if current_positions >= max_trades and symbol in open_pos:
            print_info(f"  {symbol} already has an active position - skipping to next pair")
            continue
        
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
            print(f"  {Colors.WHITE}RSI(14): {Colors.CYAN}{tech_data['momentum']['rsi14']} ({tech_data['momentum']['rsi_zone']}){Colors.RESET}")
            print(f"  {Colors.WHITE}MACD: {Colors.CYAN}{tech_data['momentum']['macd_trend']}{Colors.RESET}")
            print(f"  {Colors.WHITE}EMA Position: {Colors.CYAN}20:{tech_data['ema_levels']['price_vs_ema20']}, 50:{tech_data['ema_levels']['price_vs_ema50']}{Colors.RESET}")
            print(f"  {Colors.WHITE}BB Position: {Colors.CYAN}{tech_data['bollinger_bands']['position']}{Colors.RESET}")
            print(f"  {Colors.WHITE}Volume: {Colors.CYAN}{tech_data['volume_analysis']['ratio']:.1f}x avg{Colors.RESET}")
            print(f"  {Colors.WHITE}H1 Trend: {Colors.CYAN}{tech_data['mtf_state']['H1_trend']}{Colors.RESET}")
            print(f"  {Colors.WHITE}Session: {Colors.CYAN}{tech_data['sessions']['active']}{Colors.RESET}")
            
            # Get AI analysis
            analysis = deepseek_analyze(symbol, tech_data, account)
            
            # Create signal for this pair
            signal = {
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
                "atr": tech_data['measures']['atr_h1_points']  # ATR for reference only
            }
            
            # Add to signals list for monitoring
            signals.append(signal)
            
            # Store this signal for continuous monitoring of THIS symbol
            last_analysis_signals[symbol] = signal
            
            # IMMEDIATE DECISION FOR THIS PAIR
            print_separator()
            print_info(f"DECISION TIME FOR {symbol}")
            
            action = signal["action"].upper()
            confidence = signal["confidence"]
            
            # Display AI analysis
            print_ai_analysis(
                symbol, action, confidence,
                signal.get("entry"), signal.get("sl"), signal.get("tp")
            )
            
            # Display confidence breakdown if available
            breakdown = signal.get("confidence_breakdown", {})
            if breakdown:
                print(f"  {Colors.WHITE}Confidence Breakdown:{Colors.RESET}")
                print(f"    Quantum: {Colors.CYAN}{breakdown.get('quantum', 0)}%{Colors.RESET}")
                print(f"    Tactical: {Colors.CYAN}{breakdown.get('tactical', 0)}%{Colors.RESET}")
                print(f"    Psychological: {Colors.CYAN}{breakdown.get('psychological', 0)}%{Colors.RESET}")
                if breakdown.get('session_adjustment'):
                    adj_color = Colors.GREEN if breakdown['session_adjustment'] > 0 else Colors.YELLOW if breakdown['session_adjustment'] < 0 else Colors.WHITE
                    print(f"    Session Adjustment: {adj_color}{breakdown['session_adjustment']:+d}%{Colors.RESET}")
            
            # Display guardian status
            guardian = signal.get("guardian", {})
            if guardian:
                print(f"  {Colors.WHITE}Guardian Filters:{Colors.RESET}")
                anti_range = guardian.get('anti_range_pass', False)
                color = Colors.GREEN if anti_range else Colors.RED
                print(f"    Anti-Range: {color}{'PASS' if anti_range else 'FAIL'}{Colors.RESET}")
                
                confluence = guardian.get('confluence_pass', False)
                color = Colors.GREEN if confluence else Colors.RED
                print(f"    Confluence: {color}{'PASS' if confluence else 'FAIL'}{Colors.RESET}")
                
                max_protect = guardian.get('max_protect_pass', False)
                color = Colors.GREEN if max_protect else Colors.YELLOW
                status = 'PASS (Ultra-Tolerant)' if max_protect else 'SOFT BLOCK'
                print(f"    MaxProtect: {color}{status}{Colors.RESET}")
            
            # Check if we should execute trade for THIS pair NOW
            decision_id = str(uuid.uuid4())[:8]
            
            # Check confidence threshold
            if confidence < MIN_CONFIDENCE or action == "NO_TRADE":
                reason = f"Below threshold (min: {MIN_CONFIDENCE}%) or NO_TRADE signal"
                print_trade_decision(symbol, "SKIP", reason)
                log_trade(decision_id, symbol, action, confidence, "", "", "", status="SKIPPED", reason=reason)
                continue  # Move to next pair
            
            # Check news block
            if symbol in blocked_pairs:
                print_trade_decision(symbol, "BLOCKED", blocked_pairs[symbol])
                log_trade(decision_id, symbol, action, confidence, "", "", "", status="BLOCKED", reason=blocked_pairs[symbol])
                continue  # Move to next pair
            
            # Check trading hours
            hours_allowed, hours_reason = is_trading_hours_allowed()
            if not hours_allowed:
                print_trade_decision(symbol, "BLOCKED", f"Trading hours restriction: {hours_reason}")
                log_trade(decision_id, symbol, action, confidence, "", "", "", status="BLOCKED", reason=f"Hours: {hours_reason}")
                continue  # Move to next pair
            
            # Check if position already open for this symbol
            if symbol in open_pos:
                print_trade_decision(symbol, "MANAGED", "Position already exists for this pair")
                log_trade(decision_id, symbol, action, confidence, "", "", "", status="MANAGED", reason="Position exists")
                continue  # Move to next pair
            
            # Check if we can open new positions
            if len(open_pos) >= max_trades:
                print_trade_decision(symbol, "SKIP", f"Maximum {max_trades} positions already open")
                log_trade(decision_id, symbol, action, confidence, "", "", "", status="SKIPPED", reason="Max positions reached")
                break  # Stop analyzing remaining pairs if max reached
            
            # EXECUTE TRADE FOR THIS PAIR
            entry = signal.get("entry")
            sl = signal.get("sl")
            tp = signal.get("tp")
            
            if entry and sl and tp:
                print_trade_decision(symbol, "OPEN", f"High confidence signal ({confidence:.1f}%) - Slot available ({len(open_pos)+1}/{max_trades})")
                res = open_trade(symbol, action, float(sl), float(tp))
                
                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                    trade_id = str(res.order or res.deal or decision_id)
                    log_trade(trade_id, symbol, action, confidence, entry, sl, tp, status="OPEN", reason="Sequential analysis approved")
                    # Update open positions count after successful trade
                    open_pos[symbol] = {"action": action, "confidence": confidence}
                    print_success(f"Position opened for {symbol} - Total positions: {len(open_pos)}/{max_trades}")
                    
                    # Start monitoring for THIS symbol only
                    start_continuous_monitoring(symbol)
                    
                    # Check if we reached max positions
                    if len(open_pos) >= max_trades:
                        print_info(f"Maximum positions reached ({max_trades}). Stopping analysis.")
                        break
                else:
                    error_msg = f"Order failed: {getattr(res,'retcode',None)}"
                    print_error(error_msg)
                    log_trade(decision_id, symbol, action, confidence, entry, sl, tp, status="ERROR", reason=error_msg)
            else:
                print_warning(f"Invalid entry/SL/TP values for {symbol}")
            
        except Exception as e:
            print_error(f"Error analyzing {symbol}: {e}")
            continue
    
    # Auto-refresh existing trades with new signals (check for reversals)
    if signals:
        auto_refresh_open_trades(signals)
    
    # Check which symbols have positions and ensure monitoring is running for them
    positions = mt5.positions_get()
    if positions:
        for pos in positions:
            # Ensure monitoring is running for each symbol with a position
            start_continuous_monitoring(pos.symbol)
    
    # Summary of analysis results
    print_separator()
    print_info("SEQUENTIAL ANALYSIS COMPLETE")
    print_info(f"   Pairs analyzed: {len(signals)}")
    print_info(f"   Positions open: {len(open_positions_map())}/{max_trades}")
    
    # Skip the old duplicate signal processing loop
    return  # Exit cycle_once here
    
    # Old parallel processing code below (now unreachable)
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
            
            # MaxProtect check (ULTRA-TOLERANT)
            max_protect = guardian.get('max_protect_pass', False)
            color = Colors.GREEN if max_protect else Colors.YELLOW  # Yellow for warning, not red
            status = 'PASS (Ultra-Tolerant)' if max_protect else 'SOFT BLOCK'
            print(f"    MaxProtect: {color}{status}{Colors.RESET}")
            
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
        
        # Check if position already open for this symbol (1 per pair max)
        if symbol in open_pos:
            print_trade_decision(symbol, "MANAGED", "Position actively managed by auto-refresh system")
            log_trade(decision_id, symbol, action, confidence, "", "", "", status="MANAGED", reason="Auto-refresh active")
            continue
        
        # Check if we can open new positions (max 2 total)
        if len(open_pos) >= max_trades:
            print_trade_decision(symbol, "SKIP", f"Maximum {max_trades} positions already open")
            log_trade(decision_id, symbol, action, confidence, "", "", "", status="SKIPPED", reason="Max positions reached")
            continue
        
        # Open new position (we can open because: no position for this symbol AND total < max)
        entry = sig.get("entry")
        sl = sig.get("sl")
        tp = sig.get("tp")
        
        if entry and sl and tp:
            print_trade_decision(symbol, "OPEN", f"High confidence signal ({confidence:.1f}%) - Slot available ({len(open_pos)+1}/{max_trades})")
            res = open_trade(symbol, action, float(sl), float(tp))
            
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                trade_id = str(res.order or res.deal or decision_id)
                log_trade(trade_id, symbol, action, confidence, entry, sl, tp, status="OPEN", reason="Thanatos-Guardian approved")
                # Update open positions count after successful trade
                open_pos[symbol] = {"action": action, "confidence": confidence}
                print_success(f"✅ Position opened for {symbol} - Total positions: {len(open_pos)}/{max_trades}")
            else:
                error_msg = f"Order failed: {getattr(res,'retcode',None)}"
                print_error(error_msg)
                log_trade(decision_id, symbol, action, confidence, entry, sl, tp, status="ERROR", reason=error_msg)
            # Don't break - allow opening multiple positions up to the limit
        else:
            print_warning(f"Invalid entry/SL/TP values for {symbol}")

def main():
    # Validate configuration first
    if not validate_config():
        print_error("Configuration validation failed. Please check enhanced_config_btc_xau.py")
        return
    
    init_logger()
    print_header()
    print_info("Using Thanatos-Volume-Adaptive v16.0-VOLVOLT-TRIAD (Triple Position Strategy)")
    print_info(f"Trading instruments: {', '.join(TRADING_INSTRUMENTS)}")
    print_success(f"Position Management: Max {RISK_MANAGEMENT_CONFIG['max_concurrent_trades']} positions simultaneously (1 per pair)")
    print_info("Strategy: Continuous loop - Analyze if no position, Monitor if position exists")
    
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
    print_info(f"Check interval: 15 seconds fixed (continuous monitoring)")
    print_warning("Guardian Filters Active: Anti-Range, News Filter, MaxProtect (ULTRA-TOLERANT MODE +20%)")
    
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
        
        # Fixed 15 seconds wait for continuous monitoring
        wait = 15  # Fixed 15 seconds between cycles
        print_next_cycle(wait)
        time.sleep(wait)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_warning("\nBot stopped by user")
        stop_continuous_monitoring()  # Stop all monitoring threads
        mt5.shutdown()
    except Exception as e:
        print_error(f"Fatal error: {e}")
        stop_continuous_monitoring()  # Stop all monitoring threads
        mt5.shutdown()