"""Test script to verify division by 1.7 normalization
BTCUSD: SL / 1.7, TP / 1.7 (equivalent to x0.588)
XAUUSD: SL / 1.7, TP / 1.7 (equivalent to x0.588)
"""

from enhanced_config_btc_xau import TP_SL_ADJUSTMENT_CONFIG, get_tp_sl_adjustment
from colorful_logger import print_info, print_success, print_error

def test_normalization():
    """Test the division by 1.7 normalization"""
    
    print_info("Testing Division by 1.7 Normalization")
    print_info("=" * 60)
    print_info("")
    print_info("Formula for both instruments:")
    print_info("  SL = DeepSeek SL / 1.7 (equivalent to x0.588)")
    print_info("  TP = DeepSeek TP / 1.7 (equivalent to x0.588)")
    print_info("")
    
    # Import the adjust_tp_sl function
    from bot_enhanced import adjust_tp_sl
    
    # Test cases
    test_cases = [
        {
            'name': 'XAUUSD BUY',
            'symbol': 'XAUUSD',
            'entry': 2000.0,
            'deepseek_sl': 1990.0,  # 10 points away
            'deepseek_tp': 2020.0,  # 20 points away
            'direction': 'BUY'
        },
        {
            'name': 'BTCUSD BUY',
            'symbol': 'BTCUSD',
            'entry': 100000.0,
            'deepseek_sl': 99500.0,  # 500 points away
            'deepseek_tp': 101000.0,  # 1000 points away
            'direction': 'BUY'
        },
        {
            'name': 'XAUUSD SELL',
            'symbol': 'XAUUSD',
            'entry': 2650.0,
            'deepseek_sl': 2670.0,  # 20 points away
            'deepseek_tp': 2600.0,  # 50 points away
            'direction': 'SELL'
        }
    ]
    
    # Display current configuration
    print_info("Current Configuration:")
    print_info("-" * 40)
    for symbol in ['XAUUSD', 'BTCUSD']:
        adjustments = get_tp_sl_adjustment(symbol)
        sl_factor = adjustments.get('sl_normalization_factor', 'Not set')
        tp_factor = adjustments.get('tp_normalization_factor', 'Not set')
        print_info(f"  {symbol}:")
        print_info(f"    SL Factor: {sl_factor:.3f} (1/1.7)")
        print_info(f"    TP Factor: {tp_factor:.3f} (1/1.7)")
    
    print_info("")
    print_info("Test Results:")
    print_info("-" * 40)
    
    all_passed = True
    
    for test in test_cases:
        print_info(f"\n{test['name']}:")
        
        # Call the adjust_tp_sl function
        final_sl, final_tp = adjust_tp_sl(
            symbol=test['symbol'],
            entry=test['entry'],
            sl=test['deepseek_sl'],
            tp=test['deepseek_tp']
        )
        
        # Calculate distances
        original_sl_distance = abs(test['entry'] - test['deepseek_sl'])
        original_tp_distance = abs(test['deepseek_tp'] - test['entry'])
        actual_sl_distance = abs(test['entry'] - final_sl)
        actual_tp_distance = abs(final_tp - test['entry'])
        
        # Expected distances
        expected_sl = original_sl_distance / 1.7
        expected_tp = original_tp_distance / 1.7
        
        # Display results
        print_info(f"  DeepSeek: SL={original_sl_distance:.0f}, TP={original_tp_distance:.0f}")
        print_info(f"  Expected: SL={expected_sl:.1f}, TP={expected_tp:.1f}")
        print_info(f"  Actual:   SL={actual_sl_distance:.1f}, TP={actual_tp_distance:.1f}")
        
        # Calculate Risk/Reward
        original_rr = original_tp_distance / original_sl_distance if original_sl_distance > 0 else 0
        final_rr = actual_tp_distance / actual_sl_distance if actual_sl_distance > 0 else 0
        
        print_info(f"  Risk/Reward: {original_rr:.1f}:1 -> {final_rr:.1f}:1 (maintains ratio)")
        
        # Check if correct (with tolerance)
        sl_correct = abs(actual_sl_distance - expected_sl) < 0.5
        tp_correct = abs(actual_tp_distance - expected_tp) < 0.5
        
        if sl_correct and tp_correct:
            print_success("  [OK] Test passed!")
        else:
            print_error("  [X] Test failed!")
            all_passed = False
    
    print_info("")
    print_info("=" * 60)
    
    if all_passed:
        print_success("All tests passed! Division by 1.7 working correctly.")
        print_info("")
        print_info("Summary: Both instruments use SL/1.7 and TP/1.7")
        print_info("This reduces all distances to 58.8% of DeepSeek's suggestions")
        print_info("while maintaining the original risk/reward ratio.")
    else:
        print_error("Some tests failed!")

if __name__ == "__main__":
    test_normalization()