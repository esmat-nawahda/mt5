"""Test script to verify updated TP/SL normalization logic (1.25x SL, 0.15x TP)"""

from enhanced_config_btc_xau import TP_SL_ADJUSTMENT_CONFIG, get_tp_sl_adjustment
from colorful_logger import print_info, print_success, print_error

def test_normalization_updated():
    """Test the updated normalization calculation"""
    
    print_info("Testing Updated TP/SL Normalization Logic")
    print_info("=" * 50)
    
    # Import the adjust_tp_sl function
    from bot_enhanced import adjust_tp_sl
    
    # Test cases for BTCUSD and XAUUSD
    test_cases = [
        {
            'symbol': 'BTCUSD',
            'entry': 100000.0,
            'deepseek_sl': 99500.0,  # 500 points away
            'deepseek_tp': 101000.0,  # 1000 points away
            'expected_sl_distance': 500 * 1.25,  # 625
            'expected_tp_distance': 1000 * 0.15,  # 150
            'direction': 'BUY'
        },
        {
            'symbol': 'BTCUSD',
            'entry': 100000.0,
            'deepseek_sl': 100500.0,  # 500 points away
            'deepseek_tp': 99000.0,   # 1000 points away
            'expected_sl_distance': 500 * 1.25,  # 625
            'expected_tp_distance': 1000 * 0.15,  # 150
            'direction': 'SELL'
        },
        {
            'symbol': 'XAUUSD',
            'entry': 2000.0,
            'deepseek_sl': 1990.0,  # 10 points away
            'deepseek_tp': 2020.0,  # 20 points away
            'expected_sl_distance': 10 * 1.25,  # 12.5
            'expected_tp_distance': 20 * 0.15,  # 3
            'direction': 'BUY'
        },
        {
            'symbol': 'XAUUSD',
            'entry': 2000.0,
            'deepseek_sl': 2010.0,  # 10 points away
            'deepseek_tp': 1980.0,  # 20 points away
            'expected_sl_distance': 10 * 1.25,  # 12.5
            'expected_tp_distance': 20 * 0.15,  # 3
            'direction': 'SELL'
        }
    ]
    
    print_info(f"Configuration: use_normalization = {TP_SL_ADJUSTMENT_CONFIG.get('use_normalization')}")
    print_info(f"SL Factor: {TP_SL_ADJUSTMENT_CONFIG.get('sl_normalization_factor')}")
    print_info(f"TP Factor: {TP_SL_ADJUSTMENT_CONFIG.get('tp_normalization_factor')}")
    print_info(f"Risk/Reward Ratio: {TP_SL_ADJUSTMENT_CONFIG.get('min_risk_reward_ratio')}")
    print_info("")
    
    all_passed = True
    
    for i, test in enumerate(test_cases, 1):
        print_info(f"Test Case #{i}: {test['symbol']} {test['direction']}")
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
        
        # Verify results
        print_info(f"  Entry Price: {test['entry']}")
        print_info(f"  DeepSeek SL: {test['deepseek_sl']} (distance: {original_sl_distance})")
        print_info(f"  DeepSeek TP: {test['deepseek_tp']} (distance: {original_tp_distance})")
        print_info(f"  Final SL: {final_sl:.2f} (distance: {actual_sl_distance:.2f})")
        print_info(f"  Final TP: {final_tp:.2f} (distance: {actual_tp_distance:.2f})")
        print_info(f"  Expected SL distance: {test['expected_sl_distance']:.2f}")
        print_info(f"  Expected TP distance: {test['expected_tp_distance']:.2f}")
        
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
        
        # Calculate and display Risk/Reward ratio
        rr_ratio = actual_tp_distance / actual_sl_distance if actual_sl_distance > 0 else 0
        expected_rr = 0.15 / 1.25  # 0.12
        print_info(f"  Risk/Reward Ratio: {rr_ratio:.3f} (expected: {expected_rr:.3f})")
        print_info("")
    
    print_info("=" * 50)
    if all_passed:
        print_success("All tests passed! New normalization factors working correctly.")
        print_info("Summary of changes:")
        print_info("  - SL factor reduced from 2.5x to 1.25x (tighter stops)")
        print_info("  - TP factor remains at 0.15x (quick profits)")
        print_info("  - Risk/Reward improved from 0.06 to 0.12")
    else:
        print_error("Some tests failed! Check the implementation.")

if __name__ == "__main__":
    test_normalization_updated()