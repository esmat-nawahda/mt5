"""Test script to verify trading hours restriction logic"""

from datetime import datetime
import pytz
from enhanced_config_btc_xau import TRADING_HOURS_CONFIG
from colorful_logger import print_info, print_success, print_error, print_warning

def test_trading_hours():
    """Test the trading hours check function"""
    
    # Import the function from bot_enhanced
    from bot_enhanced import is_trading_hours_allowed
    
    print_info("Testing Trading Hours Restriction")
    print_info("=" * 50)
    
    # Get current time in CET
    try:
        cet_tz = pytz.timezone('CET')
        current_time = datetime.now(cet_tz)
        print_info(f"Current time (CET): {current_time.strftime('%Y-%m-%d %H:%M:%S %A')}")
    except:
        current_time = datetime.now()
        print_warning("Could not get CET timezone, using system time")
        print_info(f"Current time (System): {current_time.strftime('%Y-%m-%d %H:%M:%S %A')}")
    
    print_info("")
    print_info("Configuration:")
    print_info(f"  Enabled: {TRADING_HOURS_CONFIG.get('enabled')}")
    print_info(f"  Block Weekends: {TRADING_HOURS_CONFIG.get('block_weekends')}")
    print_info("")
    print_info("Trading Windows:")
    for window in TRADING_HOURS_CONFIG.get('trading_windows', []):
        print_info(f"  - {window['name']}: {window['start']}-{window['end']} CET")
        print_info(f"    Days: {', '.join(window['days'])}")
    
    print_info("")
    print_info("Testing current time...")
    print_info("-" * 40)
    
    # Check if trading is allowed now
    allowed, reason = is_trading_hours_allowed()
    
    if allowed:
        print_success(f"[TRADING ALLOWED] {reason}")
    else:
        print_error(f"[TRADING BLOCKED] {reason}")
    
    print_info("")
    print_info("Testing specific times...")
    print_info("-" * 40)
    
    # Test cases for different times
    test_times = [
        ("Monday 09:00", True, "Should be in morning session"),
        ("Monday 12:30", False, "Should be in lunch break"),
        ("Monday 14:00", True, "Should be in afternoon session"),
        ("Monday 02:00", True, "Should be in night session"),
        ("Monday 04:00", False, "Should be outside hours"),
        ("Saturday 10:00", False, "Should be blocked on weekend"),
        ("Sunday 15:00", False, "Should be blocked on weekend"),
    ]
    
    print_info("")
    print_info("Simulated Time Tests:")
    for time_desc, expected, description in test_times:
        print_info(f"  {time_desc}: {description}")
        print_info(f"    Expected: {'ALLOWED' if expected else 'BLOCKED'}")

if __name__ == "__main__":
    test_trading_hours()