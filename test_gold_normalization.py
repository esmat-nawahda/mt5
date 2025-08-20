"""Test script to verify XAUUSD normalization factor update (1.05x SL)"""

from enhanced_config_btc_xau import TP_SL_ADJUSTMENT_CONFIG, get_tp_sl_adjustment
from colorful_logger import print_info, print_success, print_error

def test_gold_normalization():
    """Test the updated XAUUSD normalization factor"""
    
    print_info("Testing Updated XAUUSD Normalization (1.05x SL)")
    print_info("=" * 60)
    
    # Import the adjust_tp_sl function
    from bot_enhanced import adjust_tp_sl
    
    # Test cases for XAUUSD with new 1.05x factor
    test_cases = [
        {
            'symbol': 'XAUUSD',
            'entry': 2000.0,
            'deepseek_sl': 1990.0,  # 10 points away
            'deepseek_tp': 2020.0,  # 20 points away
            'expected_sl_factor': 1.05,
            'expected_tp_factor': 0.15,
            'expected_sl_distance': 10 * 1.05,  # 10.5
            'expected_tp_distance': 20 * 0.15,  # 3
            'expected_rr': 0.15 / 1.05,  # 0.143
            'direction': 'BUY'
        },
        {
            'symbol': 'XAUUSD',
            'entry': 2000.0,
            'deepseek_sl': 2010.0,  # 10 points away
            'deepseek_tp': 1980.0,  # 20 points away
            'expected_sl_factor': 1.05,
            'expected_tp_factor': 0.15,
            'expected_sl_distance': 10 * 1.05,  # 10.5
            'expected_tp_distance': 20 * 0.15,  # 3
            'expected_rr': 0.15 / 1.05,  # 0.143
            'direction': 'SELL'
        },
        {
            'symbol': 'XAUUSD',
            'entry': 2650.0,
            'deepseek_sl': 2630.0,  # 20 points away
            'deepseek_tp': 2700.0,  # 50 points away
            'expected_sl_factor': 1.05,
            'expected_tp_factor': 0.15,
            'expected_sl_distance': 20 * 1.05,  # 21
            'expected_tp_distance': 50 * 0.15,  # 7.5
            'expected_rr': 0.15 / 1.05,  # 0.143
            'direction': 'BUY'
        },
        # Also test BTCUSD to ensure it still uses 1.15
        {
            'symbol': 'BTCUSD',
            'entry': 100000.0,
            'deepseek_sl': 99500.0,  # 500 points away
            'deepseek_tp': 101000.0,  # 1000 points away
            'expected_sl_factor': 1.15,
            'expected_tp_factor': 0.15,
            'expected_sl_distance': 500 * 1.15,  # 575
            'expected_tp_distance': 1000 * 0.15,  # 150
            'expected_rr': 0.15 / 1.15,  # 0.130
            'direction': 'BUY'
        }
    ]
    
    # Display configuration
    print_info("Configuration:")
    for symbol in ['XAUUSD', 'BTCUSD']:
        adjustments = get_tp_sl_adjustment(symbol)
        sl_factor = adjustments.get('sl_normalization_factor', 'Not set')
        tp_factor = adjustments.get('tp_normalization_factor', 'Not set')
        rr_ratio = adjustments.get('min_risk_reward_ratio', 'Not set')
        print_info(f"  {symbol}: SL ×{sl_factor}, TP ×{tp_factor}, RR: {rr_ratio}")
    
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
        print_info(f"  Entry: {test['entry']:.2f}")
        print_info(f"  DeepSeek SL: {test['deepseek_sl']:.2f} (distance: {original_sl_distance:.2f})")
        print_info(f"  DeepSeek TP: {test['deepseek_tp']:.2f} (distance: {original_tp_distance:.2f})")
        print_info(f"  Expected Factor: SL ×{test['expected_sl_factor']}, TP ×{test['expected_tp_factor']}")
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
        
        # Calculate and display Risk/Reward
        rr_ratio = actual_tp_distance / actual_sl_distance if actual_sl_distance > 0 else 0
        print_info(f"  Risk/Reward: {rr_ratio:.3f} (expected: ~{test['expected_rr']:.3f})")
        print_info("")
    
    print_info("=" * 60)
    if all_passed:
        print_success("All tests passed! Gold normalization updated correctly.")
        print_info("")
        print_info("Summary of Current Settings:")
        print_info("  XAUUSD: SL × 1.05 (very tight stops)")
        print_info("  BTCUSD: SL × 1.15 (moderate stops)")
        print_info("  Both: TP × 0.15 (quick profits)")
        print_info("")
        print_info("Gold now uses 1.05x for very tight stop losses,")
        print_info("allowing for more precise risk management.")
    else:
        print_error("Some tests failed! Check the implementation.")

if __name__ == "__main__":
    test_gold_normalization()