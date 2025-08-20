"""Test script to verify instrument-specific normalization factors"""

from enhanced_config_btc_xau import TP_SL_ADJUSTMENT_CONFIG, get_tp_sl_adjustment
from colorful_logger import print_info, print_success, print_error

def test_instrument_normalization():
    """Test instrument-specific normalization factors"""
    
    print_info("Testing Instrument-Specific Normalization Factors")
    print_info("=" * 60)
    
    # Import the adjust_tp_sl function
    from bot_enhanced import adjust_tp_sl
    
    # Test cases for BTCUSD (1.15x SL) and XAUUSD (1.25x SL)
    test_cases = [
        {
            'symbol': 'BTCUSD',
            'entry': 100000.0,
            'deepseek_sl': 99500.0,  # 500 points away
            'deepseek_tp': 101000.0,  # 1000 points away
            'expected_sl_factor': 1.15,
            'expected_tp_factor': 0.15,
            'expected_sl_distance': 500 * 1.15,  # 575
            'expected_tp_distance': 1000 * 0.15,  # 150
            'expected_rr': 0.15 / 1.15,  # 0.13
            'direction': 'BUY'
        },
        {
            'symbol': 'BTCUSD',
            'entry': 100000.0,
            'deepseek_sl': 100500.0,  # 500 points away
            'deepseek_tp': 99000.0,   # 1000 points away
            'expected_sl_factor': 1.15,
            'expected_tp_factor': 0.15,
            'expected_sl_distance': 500 * 1.15,  # 575
            'expected_tp_distance': 1000 * 0.15,  # 150
            'expected_rr': 0.15 / 1.15,  # 0.13
            'direction': 'SELL'
        },
        {
            'symbol': 'XAUUSD',
            'entry': 2000.0,
            'deepseek_sl': 1990.0,  # 10 points away
            'deepseek_tp': 2020.0,  # 20 points away
            'expected_sl_factor': 1.25,
            'expected_tp_factor': 0.15,
            'expected_sl_distance': 10 * 1.25,  # 12.5
            'expected_tp_distance': 20 * 0.15,  # 3
            'expected_rr': 0.15 / 1.25,  # 0.12
            'direction': 'BUY'
        },
        {
            'symbol': 'XAUUSD',
            'entry': 2000.0,
            'deepseek_sl': 2010.0,  # 10 points away
            'deepseek_tp': 1980.0,  # 20 points away
            'expected_sl_factor': 1.25,
            'expected_tp_factor': 0.15,
            'expected_sl_distance': 10 * 1.25,  # 12.5
            'expected_tp_distance': 20 * 0.15,  # 3
            'expected_rr': 0.15 / 1.25,  # 0.12
            'direction': 'SELL'
        }
    ]
    
    # Display configuration
    print_info("Global Configuration:")
    print_info(f"  use_normalization: {TP_SL_ADJUSTMENT_CONFIG.get('use_normalization')}")
    print_info("")
    
    print_info("Instrument-Specific Factors:")
    for symbol in ['BTCUSD', 'XAUUSD']:
        adjustments = get_tp_sl_adjustment(symbol)
        sl_factor = adjustments.get('sl_normalization_factor', 'Not set')
        tp_factor = adjustments.get('tp_normalization_factor', 'Not set')
        rr_ratio = adjustments.get('min_risk_reward_ratio', 'Not set')
        print_info(f"  {symbol}:")
        print_info(f"    SL Factor: {sl_factor}")
        print_info(f"    TP Factor: {tp_factor}")
        print_info(f"    RR Ratio: {rr_ratio}")
    
    print_info("")
    print_info("Running Test Cases...")
    print_info("-" * 60)
    
    all_passed = True
    
    for i, test in enumerate(test_cases, 1):
        print_info(f"Test #{i}: {test['symbol']} {test['direction']}")
        
        # Call the adjust_tp_sl function
        final_sl, final_tp = adjust_tp_sl(
            symbol=test['symbol'],
            entry=test['entry'],
            sl=test['deepseek_sl'],
            tp=test['deepseek_tp']
        )
        
        # Calculate actual distances
        actual_sl_distance = abs(test['entry'] - final_sl)
        actual_tp_distance = abs(final_tp - test['entry'])
        
        # Calculate original DeepSeek distances
        original_sl_distance = abs(test['entry'] - test['deepseek_sl'])
        original_tp_distance = abs(test['deepseek_tp'] - test['entry'])
        
        # Display results
        print_info(f"  Entry: {test['entry']}")
        print_info(f"  DeepSeek SL: {test['deepseek_sl']} (distance: {original_sl_distance})")
        print_info(f"  DeepSeek TP: {test['deepseek_tp']} (distance: {original_tp_distance})")
        print_info(f"  Expected SL Factor: {test['expected_sl_factor']}")
        print_info(f"  Expected TP Factor: {test['expected_tp_factor']}")
        print_info(f"  Final SL: {final_sl:.2f} (distance: {actual_sl_distance:.2f})")
        print_info(f"  Final TP: {final_tp:.2f} (distance: {actual_tp_distance:.2f})")
        
        # Check if calculations are correct
        sl_correct = abs(actual_sl_distance - test['expected_sl_distance']) < 0.01
        tp_correct = abs(actual_tp_distance - test['expected_tp_distance']) < 0.01
        
        if sl_correct and tp_correct:
            print_success(f"  [OK] Test passed!")
        else:
            print_error(f"  [X] Test failed!")
            all_passed = False
            if not sl_correct:
                print_error(f"    SL mismatch: expected {test['expected_sl_distance']:.2f}, got {actual_sl_distance:.2f}")
            if not tp_correct:
                print_error(f"    TP mismatch: expected {test['expected_tp_distance']:.2f}, got {actual_tp_distance:.2f}")
        
        # Calculate and verify Risk/Reward
        rr_ratio = actual_tp_distance / actual_sl_distance if actual_sl_distance > 0 else 0
        print_info(f"  Risk/Reward: {rr_ratio:.3f} (expected: {test['expected_rr']:.3f})")
        print_info("")
    
    print_info("=" * 60)
    if all_passed:
        print_success("All tests passed! Instrument-specific normalization working correctly.")
        print_info("")
        print_info("Summary:")
        print_info("  BTCUSD: SL × 1.15, TP × 0.15 (RR: 0.13)")
        print_info("  XAUUSD: SL × 1.25, TP × 0.15 (RR: 0.12)")
        print_info("  Bitcoin uses tighter stops (1.15x) due to higher precision")
        print_info("  Gold uses wider stops (1.25x) for volatility protection")
    else:
        print_error("Some tests failed! Check the implementation.")

if __name__ == "__main__":
    test_instrument_normalization()