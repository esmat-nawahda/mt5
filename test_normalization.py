"""Test script to verify TP/SL normalization logic"""

from enhanced_config_btc_xau import TP_SL_ADJUSTMENT_CONFIG, get_tp_sl_adjustment
from colorful_logger import print_info, print_success, print_error

def test_normalization():
    """Test the normalization calculation"""
    
    print_info("Testing TP/SL Normalization Logic")
    print_info("=" * 50)
    
    # Import the adjust_tp_sl function
    from bot_enhanced import adjust_tp_sl
    
    # Test cases for BTCUSD
    test_cases = [
        {
            'symbol': 'BTCUSD',
            'entry': 100000.0,
            'deepseek_sl': 99500.0,  # 500 points away
            'deepseek_tp': 101000.0,  # 1000 points away
            'expected_sl_distance': 500 * 2.5,  # 1250
            'expected_tp_distance': 1000 * 0.15,  # 150
            'direction': 'BUY'
        },
        {
            'symbol': 'BTCUSD',
            'entry': 100000.0,
            'deepseek_sl': 100500.0,  # 500 points away
            'deepseek_tp': 99000.0,   # 1000 points away
            'expected_sl_distance': 500 * 2.5,  # 1250
            'expected_tp_distance': 1000 * 0.15,  # 150
            'direction': 'SELL'
        },
        {
            'symbol': 'XAUUSD',
            'entry': 2000.0,
            'deepseek_sl': 1990.0,  # 10 points away
            'deepseek_tp': 2020.0,  # 20 points away
            'expected_sl_distance': 10 * 2.5,  # 25
            'expected_tp_distance': 20 * 0.15,  # 3
            'direction': 'BUY'
        },
        {
            'symbol': 'XAUUSD',
            'entry': 2000.0,
            'deepseek_sl': 2010.0,  # 10 points away
            'deepseek_tp': 1980.0,  # 20 points away
            'expected_sl_distance': 10 * 2.5,  # 25
            'expected_tp_distance': 20 * 0.15,  # 3
            'direction': 'SELL'
        }
    ]
    
    print_info(f"Configuration: use_normalization = {TP_SL_ADJUSTMENT_CONFIG.get('use_normalization')}")
    print_info(f"SL Factor: {TP_SL_ADJUSTMENT_CONFIG.get('sl_normalization_factor')}")
    print_info(f"TP Factor: {TP_SL_ADJUSTMENT_CONFIG.get('tp_normalization_factor')}")
    print_info("")
    
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
            if not sl_correct:
                print_error(f"    SL mismatch: expected {test['expected_sl_distance']:.2f}, got {actual_sl_distance:.2f}")
            if not tp_correct:
                print_error(f"    TP mismatch: expected {test['expected_tp_distance']:.2f}, got {actual_tp_distance:.2f}")
        
        # Calculate and display Risk/Reward ratio
        rr_ratio = actual_tp_distance / actual_sl_distance if actual_sl_distance > 0 else 0
        print_info(f"  Risk/Reward Ratio: {rr_ratio:.3f}")
        print_info("")

if __name__ == "__main__":
    test_normalization()