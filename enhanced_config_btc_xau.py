# enhanced_config_btc_xau.py
"""
Complete configuration for DeepSeek-MT5 system
Trading only: BTCUSD and XAUUSD
Version: 2.0.0-BTCXAU
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ================================================================
# 🎯 TRADING INSTRUMENTS - BTCUSD AND XAUUSD ONLY
# ================================================================

TRADING_INSTRUMENTS = ['BTCUSD', 'XAUUSD']  # ✅ ONLY THESE TWO PAIRS

# Specific configuration per instrument
INSTRUMENTS_CONFIG = {
    'XAUUSD': {
        'name': 'Gold vs US Dollar',
        'type': 'precious_metal',
        'news_currencies': ['USD'],
        'range_atr_ratio': 0.5,          # Gold more sensitive to range
        'spread_max_pips': 3.0,
        'tp_sl_adjustment': {
            'tp_reduction_factor': 0.6,   # TP reduced to 60% for gold
            'sl_increase_factor': 1.1     # SL increased by 10% only
        },
        'min_pip_value': 10,             # $10 per point for gold
        'precision': 2,                  # 2 decimals for gold
        'trading_hours': '24/5',
        'volatility': 'medium'
    },
    'BTCUSD': {
        'name': 'Bitcoin vs US Dollar',
        'type': 'cryptocurrency',
        'news_currencies': ['USD'],
        'range_atr_ratio': 0.7,          # Bitcoin less sensitive to range
        'spread_max_pips': 5.0,
        'tp_sl_adjustment': {
            'tp_reduction_factor': 0.65,  # TP reduced to 65% for Bitcoin
            'sl_increase_factor': 1.15    # SL increased by 15%
        },
        'min_pip_value': 1,              # $1 per point for Bitcoin
        'precision': 2,                  # 2 decimals for Bitcoin
        'trading_hours': '24/7',
        'volatility': 'high'
    }
}

# ================================================================
# 📰 FOREXFACTORY NEWS CONFIGURATION
# ================================================================

NEWS_FILTERING_CONFIG = {
    'news_window_minutes': 45,           # 45 minutes before/after red news
    'dangerous_news_impacts': ['High', 'Red'],
    'currency_monitoring': {
        'XAUUSD': ['USD'],               # Gold: monitor USD only
        'BTCUSD': ['USD']                # Bitcoin: monitor USD only
    },
    'cache_timeout_minutes': 5,
    'retry_attempts': 3,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'forexfactory_url': 'https://www.forexfactory.com/calendar',
    'headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }
}

# ================================================================
# 🚫 FLAT RANGE DETECTION CONFIGURATION
# ================================================================

RANGE_DETECTION_CONFIG = {
    'range_atr_ratio': 0.8,              # Range if amplitude < 80% ATR (very tolerant)
    'range_min_candles': 20,             # Minimum 20 candles to confirm (stricter confirmation)
    'breakout_threshold': 1.2,           # Lower breakout threshold (easier to break out)
    'compression_threshold': 0.4,        # Lower compression score (more tolerant)
    'timeframes': ['M15', 'H1'],         # Timeframes analyzed for range
    'atr_periods': 14,                   # Periods for ATR calculation
    'instruments_specific': {
        'XAUUSD': {
            'range_atr_ratio': 0.85,     # Range if BB width < 85% ATR (very tolerant)
            'range_min_candles': 8,      # 8 candles sufficient to confirm the range
            'compression_threshold': 0.4  # 40% compression (very tolerant)
        },
        'BTCUSD': {
            'range_atr_ratio': 0.9,      # Range if BB width < 90% ATR (extremely tolerant)
            'range_min_candles': 6,      # 6 candles sufficient to confirm the range
            'compression_threshold': 0.3  # 30% compression (extremely tolerant)
        }
    }
}

# ================================================================
# 🎯 TP/SL ADJUSTMENT CONFIGURATION
# ================================================================

TP_SL_ADJUSTMENT_CONFIG = {
    'use_atr_adjustment': True,         # Enable ATR-based adjustment
    'use_normalization': False,         # Disabled - using ATR rules
    'use_fixed_pips': False,            # Disabled - using ATR rules
    'use_support_resistance': False,    # Disabled - using ATR rules
    'atr_sl_multiplier': 1.0,          # SL = max(min_pips, 1×ATR)
    'atr_tp_multiplier': 1.5,          # TP = max(min_pips, 1.5×ATR)
    'sl_buffer_pips': 100,              # Not used when ATR enabled
    'tp_buffer_pips': 10,               # Not used when ATR enabled
    'min_risk_reward_ratio': 1.5,       # Minimum R:R ratio expected
    'max_spread_multiplier': 3.0,        # Minimum SL = 3x spread
    
    # Specific adjustments per instrument
    'instruments_adjustments': {
        'XAUUSD': {
            # ATR-based adjustment for Gold
            'atr_sl_multiplier': 1.0,          # SL = max(70 pips, 1×ATR)
            'atr_tp_multiplier': 1.5,          # TP = max(140 pips, 1.5×ATR)
            'min_risk_reward_ratio': 1.5,      # Expected minimum R:R
            # Minimum fixed pip values for Gold (used with ATR)
            'min_sl_pips': 70,             # Minimum SL distance: 70 pips
            'min_tp_pips': 140,            # Minimum TP distance: 140 pips
            # Legacy fixed values (for reference)
            'fixed_sl_pips_buy': 70,       # Gold BUY: SL at entry - 70 pips
            'fixed_tp_pips_buy': 140,      # Gold BUY: TP at entry + 140 pips
            'fixed_sl_pips_sell': 70,      # Gold SELL: SL at entry + 70 pips
            'fixed_tp_pips_sell': 140,     # Gold SELL: TP at entry - 140 pips
            # Old factor-based values (not used)
            'tp_reduction_factor': 0.20,
            'sl_increase_factor': 1.8,
            'max_sl_points': 120,
            'min_tp_points': 5,
            'min_sl_points': 25
        },
        'BTCUSD': {
            # ATR-based adjustment for Bitcoin
            'atr_sl_multiplier': 1.0,          # SL = max(40 pips, 1×ATR)
            'atr_tp_multiplier': 1.5,          # TP = max(65 pips, 1.5×ATR)
            'min_risk_reward_ratio': 1.5,      # Expected minimum R:R
            # Minimum fixed pip values for Bitcoin (used with ATR)
            'min_sl_pips': 40,             # Minimum SL distance: 40 pips
            'min_tp_pips': 65,             # Minimum TP distance: 65 pips
            # Legacy fixed values (for reference)
            'fixed_sl_pips_buy': 40,       # BTC BUY: SL at entry - 40 pips
            'fixed_tp_pips_buy': 65,       # BTC BUY: TP at entry + 65 pips
            'fixed_sl_pips_sell': 40,      # BTC SELL: SL at entry + 40 pips
            'fixed_tp_pips_sell': 65,      # BTC SELL: TP at entry - 65 pips
            # Old factor-based values (not used)
            'tp_reduction_factor': 0.15,
            'sl_increase_factor': 4.7,
            'max_sl_points': 1200,
            'min_tp_points': 15,
            'min_sl_points': 250
        }
    },
    
    # Level validation
    'validation': {
        'check_recent_volatility': True,
        'adjust_for_spread': True,
        'respect_support_resistance': True,
        'minimum_distance_factor': 1.5
    }
}

# ================================================================
# 💰 RISK MANAGEMENT CONFIGURATION
# ================================================================

RISK_MANAGEMENT_CONFIG = {
    'max_concurrent_trades': 2,          # Maximum 2 concurrent trades (1 per instrument)
    'max_daily_trades': 20,              # Maximum 20 trades per day
    'max_risk_percent_per_trade': 2.0,   # 2% maximum per trade
    'max_daily_risk_percent': 6.0,       # 6% maximum per day
    
    # Dynamic lot sizing configuration
    'dynamic_lot_sizing': {
        'enabled': True,                 # Enable dynamic lot sizing
        'base_lot_size': 1.0,           # Minimum lot size
        'starting_capital': 10000.0,     # Starting account balance (adjust to your actual balance)
        'capital_increment': 5000.0,     # Capital change threshold ($5000)
        'lot_increment': 0.5,           # Lot size change per threshold (+/-0.5)
        'min_lot_size': 1.0             # Absolute minimum lot size
    },
    
    
    # Stop Loss Elevation to Breakeven
    'sl_to_breakeven': {
        'enabled': True,                 # Enable SL to breakeven feature
        'profit_threshold': 50,          # Move to breakeven at $50 profit
        'buffer_pips': {
            'XAUUSD': 2,                # 2 pips buffer for Gold
            'BTCUSD': 2                 # 2 points buffer for Bitcoin
        },
        'check_interval': 'every_cycle'  # Check on every cycle
    },
    
    # Trailing stop
    'trailing_stop': {
        'enabled': True,                 # Enable trailing stop
        'activation_profit': 60,         # Activate after +$60 profit
        'trail_distance_points': {
            'XAUUSD': 10,               # Trail 10 pips for gold (converted to points)
            'BTCUSD': 10                # Trail 10 pips for Bitcoin (converted to points)
        },
        'step_size': 1,                 # Adjustment in steps of 1 point for precision
        'max_trail_distance': 100,     # Max trailing distance
        'dynamic_mode': True,           # Enable dynamic trailing
        'update_frequency': 'every_tick' # Update on every price change
    },
    
    # Emergency limits
    'emergency_limits': {
        'max_drawdown_percent': 10.0,   # Stop if drawdown > 10%
        'max_consecutive_losses': 5,    # Stop after 5 consecutive losses
        'daily_loss_limit_percent': 5.0, # Stop if daily loss > 5%
        'pause_duration_minutes': 240   # 4h pause after emergency stop
    }
}

# ================================================================
# 🔄 SYSTEM CONFIGURATION
# ================================================================

SYSTEM_CONFIG = {
    'cycle_interval_seconds': int(os.getenv('CYCLE_INTERVAL_SECONDS', 120)),  # 2 minutes default
    'max_api_calls_per_hour': 100,      # DeepSeek API limit
    'timeout_seconds': 30,               # Request timeout
    'log_level': os.getenv('LOG_LEVEL', 'INFO'),
    'log_file': os.getenv('LOG_FILE', 'deepseek_mt5_btc_xau.log'),
    'max_log_size_mb': 50,              # Max log file size
    'log_backup_count': 5,              # Number of log backups
    
    # MT5 Configuration
    'mt5_config': {
        'login': int(os.getenv('MT5_LOGIN', 0)),
        'password': os.getenv('MT5_PASSWORD', ''),
        'server': os.getenv('MT5_SERVER', ''),
        'path': os.getenv('MT5_PATH', ''),
        'magic_number': 20250819,        # Unique magic number
        'slippage': 3,                   # Allowed slippage
        'retry_attempts': 3,
        'connection_timeout': 10,
        'reconnect_delay': 5
    },
    
    # DeepSeek Configuration
    'deepseek_config': {
        'api_key': os.getenv('LLM_API_KEY', os.getenv('DEEPSEEK_API_KEY', '')),
        'base_url': os.getenv('LLM_URL', 'https://api.deepseek.com/v1'),
        'model': os.getenv('LLM_MODEL', 'deepseek-reasoner'),
        'max_tokens': 8000,
        'temperature': 0.1,              # More deterministic responses
        'timeout': 30,
        'retry_attempts': 2,
        'rate_limit_per_hour': 100
    },
    
    # Execution speed optimization
    'execution_optimization': {
        'enabled': True,
        'trade_execution_timeout': 5,        # 5 seconds max for trade execution
        'pre_calculate_sizes': True,         # Pre-calculate position sizes
        'async_operations': True,            # Use async operations where possible
        'order_type_priority': 'market',     # Use market orders for speed
        'slippage_tolerance': 3,             # Max 3 pips slippage
        'retry_attempts': 2,                 # Max 2 retry attempts for failed orders
        'fast_mode': True                    # Enable all speed optimizations
    },
    
    # Monitoring and alerts
    'monitoring': {
        'enable_email_alerts': False,
        'enable_telegram_alerts': False,
        'enable_slack_alerts': False,
        'performance_check_interval': 3600,  # Performance check every hour
        'health_check_interval': 300,        # Health check every 5min
        'backup_interval': 86400             # Daily backup
    }
}

# ================================================================
# ⏰ TRADING HOURS CONFIGURATION
# ================================================================

TRADING_HOURS_CONFIG = {
    'enabled': True,  # Enable trading hours restriction
    'timezone': 'CET',  # Central European Time
    'trading_windows': [
        {
            'name': 'Morning Session',
            'start': '08:00',  # 08:00 CET
            'end': '12:00',    # 12:00 CET
            'days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        },
        {
            'name': 'Afternoon/Night Session',
            'start': '13:00',  # 13:00 CET
            'end': '03:00',    # 03:00 CET (next day)
            'days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        }
    ],
    'block_weekends': True,  # No trading on weekends
    'check_holidays': False,  # Holiday calendar check (future enhancement)
    'force_close_outside_hours': False,  # Don't close positions outside hours
    'allow_position_management': True  # Allow SL/TP updates outside hours
}

# ================================================================
# 📊 PROMPT CONFIGURATION FOR BTCUSD AND XAUUSD
# ================================================================

PROMPT_CONFIG = {
    'instruments_focus': 'BTCUSD and XAUUSD only',
    'analysis_depth': 'Deep technical analysis required',
    'timeframes': ['M15', 'H1', 'H4'],
    'confluence_minimum': 4,
    'risk_reward_minimum': 1.5,
    'min_confidence_threshold': 70,
    
    'specific_instructions': {
        'XAUUSD': [
            "Analyze DXY impact on gold",
            "Monitor psychological levels (2000, 2100, etc.)",
            "Watch interest rate correlations",
            "Consider Asian/American session volatility",
            "Geopolitical factors and inflation"
        ],
        'BTCUSD': [
            "Analyze major resistance/support levels",
            "Monitor volumes and institutional adoption",
            "Watch for weekend gaps and crypto volatility",
            "Consider tech indices correlations (NASDAQ)",
            "Impact of regulations and crypto news"
        ]
    },
    
    'output_format_requirements': [
        "SIGNAL: [BUY/SELL/NO_TRADE] [SYMBOL]",
        "ENTRY: [exact_price]",
        "STOP_LOSS: [price_with_justification]",
        "TAKE_PROFIT: [realistic_price]",
        "CONFLUENCE: [minimum_4_elements]",
        "PROBABILITY: [percentage]"
    ]
}

# ================================================================
# 🔒 SECURITY CONFIGURATION
# ================================================================

SECURITY_CONFIG = {
    'api_key_validation': True,
    'connection_encryption': True,
    'log_sensitive_data': False,
    'backup_encryption': True,
    'session_timeout': 3600,
    'max_login_attempts': 3,
    'lockout_duration': 300,
    
    # Input validation
    'input_validation': {
        'max_price_deviation': 0.1,
        'allowed_symbols': TRADING_INSTRUMENTS,
        'max_sl_distance': 1000,
        'max_tp_distance': 2000
    }
}

# ================================================================
# 🚀 COMPLETE FINAL CONFIGURATION
# ================================================================

COMPLETE_CONFIG = {
    **SYSTEM_CONFIG,
    'trading_instruments': TRADING_INSTRUMENTS,
    'instruments_config': INSTRUMENTS_CONFIG,
    'news_filtering': NEWS_FILTERING_CONFIG,
    'range_detection': RANGE_DETECTION_CONFIG,
    'tp_sl_adjustment': TP_SL_ADJUSTMENT_CONFIG,
    'risk_management': RISK_MANAGEMENT_CONFIG,
    'trading_hours': TRADING_HOURS_CONFIG,
    'prompt_config': PROMPT_CONFIG,
    'security': SECURITY_CONFIG
}

# ================================================================
# 📝 CONFIGURATION VALIDATION
# ================================================================

def validate_config():
    """Validate that the configuration is consistent"""
    errors = []
    warnings = []
    
    # Check that only BTCUSD and XAUUSD are configured
    if set(TRADING_INSTRUMENTS) != {'BTCUSD', 'XAUUSD'}:
        errors.append("ERROR: Only BTCUSD and XAUUSD should be configured")
    
    # Check that each instrument has its configuration
    for instrument in TRADING_INSTRUMENTS:
        if instrument not in INSTRUMENTS_CONFIG:
            errors.append(f"ERROR: Missing configuration for {instrument}")
    
    # Check critical environment variables
    required_env_vars = ['LLM_API_KEY', 'MT5_LOGIN', 'MT5_PASSWORD', 'MT5_SERVER']
    for var in required_env_vars:
        if not os.getenv(var):
            warnings.append(f"WARNING: Environment variable {var} missing")
    
    
    # Display results
    if errors:
        print("❌ CONFIGURATION ERRORS:")
        for error in errors:
            print(f"   {error}")
        return False
    
    if warnings:
        print("⚠️ WARNINGS:")
        for warning in warnings:
            print(f"   {warning}")
    
    print("✅ BTCUSD and XAUUSD configuration validated successfully")
    print(f"📊 Instruments: {', '.join(TRADING_INSTRUMENTS)}")
    print(f"📰 News window: ±{NEWS_FILTERING_CONFIG['news_window_minutes']} minutes")
    print(f"🎯 Range ATR ratio: {RANGE_DETECTION_CONFIG['range_atr_ratio']}")
    print(f"💰 Max risk per trade: {RISK_MANAGEMENT_CONFIG['max_risk_percent_per_trade']}%")
    
    return True

def get_instrument_config(symbol: str) -> dict:
    """Get configuration for a specific instrument"""
    return INSTRUMENTS_CONFIG.get(symbol, {})

def get_trading_hours(symbol: str) -> str:
    """Get trading hours for an instrument"""
    config = get_instrument_config(symbol)
    return config.get('trading_hours', '24/5')

def is_instrument_allowed(symbol: str) -> bool:
    """Check if an instrument is allowed"""
    return symbol in TRADING_INSTRUMENTS


def get_tp_sl_adjustment(symbol: str) -> dict:
    """Get TP/SL adjustment configuration for an instrument"""
    return TP_SL_ADJUSTMENT_CONFIG['instruments_adjustments'].get(symbol, {})

# ================================================================
# 🧪 CONFIGURATION TEST
# ================================================================

if __name__ == "__main__":
    print("🔧 DeepSeek-MT5 Configuration Test")
    print("=" * 50)
    
    # Validate configuration
    if validate_config():
        print("\n📋 Detailed configuration:")
        print(f"   Cycle interval: {SYSTEM_CONFIG['cycle_interval_seconds']}s")
        print(f"   Log level: {SYSTEM_CONFIG['log_level']}")
        print(f"   Max trades/day: {RISK_MANAGEMENT_CONFIG['max_daily_trades']}")
        print(f"   Trailing stop: +${RISK_MANAGEMENT_CONFIG['trailing_stop']['activation_profit']}")
        
        print("\n🎯 Configuration per instrument:")
        for instrument in TRADING_INSTRUMENTS:
            config = get_instrument_config(instrument)
            print(f"   {instrument}:")
            print(f"     - TP factor: {config['tp_sl_adjustment']['tp_reduction_factor']}")
            print(f"     - SL factor: {config['tp_sl_adjustment']['sl_increase_factor']}")
            print(f"     - Range ratio: {config['range_atr_ratio']}")
    else:
        print("\n❌ Invalid configuration - check errors above")
        exit(1)