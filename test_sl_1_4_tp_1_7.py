"""Test script to verify SL/1.4 and TP/1.7 normalization
BTCUSD: SL / 1.4 (x0.714), TP / 1.7 (x0.588)
XAUUSD: SL / 1.4 (x0.714), TP / 1.7 (x0.588)
"""

from enhanced_config_btc_xau import TP_SL_ADJUSTMENT_CONFIG, get_tp_sl_adjustment
from colorful_logger import print_info, print_success, print_error, print_warning

def test_asymmetric_normalization():
    """Test the SL/1.4 and TP/1.7 normalization"""
    
    print_info("Testing Asymmetric Normalization (SL/1.4, TP/1.7)")
    print_info("=" * 60)
    print_info("")
    print_info("Formula for both instruments:")
    print_info("  SL = DeepSeek SL / 1.4 (equivalent to x0.714)")
    print_info("  TP = DeepSeek TP / 1.7 (equivalent to x0.588)")
    print_info("")
    
    # Import the adjust_tp_sl function
    from bot_enhanced import adjust_tp_sl
    
    # Test cases
    test_cases = [
        {
            'name': 'XAUUSD BUY - Asymmetric factors',
            'symbol': 'XAUUSD',
            'entry': 2000.0,
            'deepseek_sl': 1990.0,  # 10 points away
            'deepseek_tp': 2020.0,  # 20 points away
            'expected_sl_distance': 10 / 1.4,  # 7.14
            'expected_tp_distance': 20 / 1.7,  # 11.76
            'direction': 'BUY'
        },
        {
            'name': 'XAUUSD SELL - Asymmetric factors',
            'symbol': 'XAUUSD',
            'entry': 2000.0,
            'deepseek_sl': 2010.0,  # 10 points away
            'deepseek_tp': 1980.0,  # 20 points away
            'expected_sl_distance': 10 / 1.4,  # 7.14
            'expected_tp_distance': 20 / 1.7,  # 11.76
            'direction': 'SELL'
        },
        {
            'name': 'BTCUSD BUY - Asymmetric factors',
            'symbol': 'BTCUSD',
            'entry': 100000.0,
            'deepseek_sl': 99500.0,  # 500 points away
            'deepseek_tp': 101000.0,  # 1000 points away
            'expected_sl_distance': 500 / 1.4,  # 357.14
            'expected_tp_distance': 1000 / 1.7,  # 588.24
            'direction': 'BUY'
        },
        {
            'name': 'BTCUSD SELL - Asymmetric factors',
            'symbol': 'BTCUSD',
            'entry': 100000.0,
            'deepseek_sl': 100500.0,  # 500 points away
            'deepseek_tp': 99000.0,   # 1000 points away
            'expected_sl_distance': 500 / 1.4,  # 357.14
            'expected_tp_distance': 1000 / 1.7,  # 588.24
            'direction': 'SELL'
        },
        {
            'name': 'Small distances test',
            'symbol': 'XAUUSD',
            'entry': 2650.0,
            'deepseek_sl': 2645.0,  # 5 points away
            'deepseek_tp': 2660.0,  # 10 points away
            'expected_sl_distance': 5 / 1.4,  # 3.57
            'expected_tp_distance': 10 / 1.7,  # 5.88
            'direction': 'BUY'
        },
        {
            'name': 'Large distances test',
            'symbol': 'BTCUSD',
            'entry': 95000.0,
            'deepseek_sl': 94000.0,  # 1000 points away
            'deepseek_tp': 97000.0,  # 2000 points away
            'expected_sl_distance': 1000 / 1.4,  # 714.29
            'expected_tp_distance': 2000 / 1.7,  # 1176.47
            'direction': 'BUY'
        }
    ]
    
    # Display current configuration
    print_info("Current Configuration:")
    print_info("-" * 40)
    for symbol in ['XAUUSD', 'BTCUSD']:
        adjustments = get_tp_sl_adjustment(symbol)
        sl_factor = adjustments.get('sl_normalization_factor', 'Not set')
        tp_factor = adjustments.get('tp_normalization_factor', 'Not set')
        rr_ratio = adjustments.get('min_risk_reward_ratio', 'Not set')
        print_info(f"  {symbol}:")
        print_info(f"    SL Factor: {sl_factor:.3f} (1/1.4)")
        print_info(f"    TP Factor: {tp_factor:.3f} (1/1.7)")
        print_info(f"    Risk/Reward: {rr_ratio:.3f}")
    
    print_info("")
    print_info("Running Test Cases...")
    print_info("=" * 60)
    
    all_passed = True
    
    for test in test_cases:
        print_info(f"\nTest: {test['name']}")
        print_info("-" * 40)
        
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
        
        # Display input
        print_info(f"  Entry Price: {test['entry']:.2f}")
        print_info(f"  DeepSeek SL: {test['deepseek_sl']:.2f} (distance: {original_sl_distance:.2f})")
        print_info(f"  DeepSeek TP: {test['deepseek_tp']:.2f} (distance: {original_tp_distance:.2f})")
        
        # Display calculation
        print_info(f"  Calculation: SL = {original_sl_distance:.2f} / 1.4 = {original_sl_distance / 1.4:.2f}")
        print_info(f"              TP = {original_tp_distance:.2f} / 1.7 = {original_tp_distance / 1.7:.2f}")
        
        # Display output
        print_info(f"  Final SL: {final_sl:.2f} (distance: {actual_sl_distance:.2f})")
        print_info(f"  Final TP: {final_tp:.2f} (distance: {actual_tp_distance:.2f})")
        
        # Check if calculations are correct (with tolerance for floating point)
        sl_correct = abs(actual_sl_distance - test['expected_sl_distance']) < 0.5
        tp_correct = abs(actual_tp_distance - test['expected_tp_distance']) < 0.5
        
        # Calculate Risk/Reward
        original_rr = original_tp_distance / original_sl_distance if original_sl_distance > 0 else 0
        final_rr = actual_tp_distance / actual_sl_distance if actual_sl_distance > 0 else 0
        
        if sl_correct and tp_correct:
            print_success(f"  [OK] Test passed!")
            print_info(f"  Original R:R: {original_rr:.2f}:1")
            print_info(f"  Final R:R: {final_rr:.2f}:1")
            print_info(f"  R:R Change: {original_rr:.2f} -> {final_rr:.2f}")
        else:
            print_error(f"  [X] Test failed!")
            all_passed = False
            if not sl_correct:
                print_error(f"    SL mismatch: expected {test['expected_sl_distance']:.2f}, got {actual_sl_distance:.2f}")
            if not tp_correct:
                print_error(f"    TP mismatch: expected {test['expected_tp_distance']:.2f}, got {actual_tp_distance:.2f}")
    
    print_info("")
    print_info("=" * 60)
    
    if all_passed:
        print_success("All tests passed! Asymmetric normalization working correctly.")
        print_info("")
        print_info("Summary:")
        print_info("  Both XAUUSD and BTCUSD now use:")
        print_info("    - SL = DeepSeek SL / 1.4 (reduces stop loss by 29%)")
        print_info("    - TP = DeepSeek TP / 1.7 (reduces take profit by 41%)")
        print_info("    - Risk/Reward = 0.824 (TP factor / SL factor)")
        print_info("")
        print_info("Effect:")
        print_info("  - Stop losses are reduced to 71.4% of DeepSeek suggestions")
        print_info("  - Take profits are reduced to 58.8% of DeepSeek suggestions")
        print_info("  - Creates tighter trading with a 0.824 risk/reward ratio")
        print_info("  - TP is reduced more than SL, creating more conservative targets")
    else:
        print_error("Some tests failed! Check the implementation.")

if __name__ == "__main__":
    test_asymmetric_normalization()