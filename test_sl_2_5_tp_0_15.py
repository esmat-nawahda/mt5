"""Test script to verify SL×2.5 and TP×0.15 normalization
BTCUSD: SL × 2.5, TP × 0.15
XAUUSD: SL × 2.5, TP × 0.15
This creates wide stops with very tight profit targets (scalping strategy)
"""

from enhanced_config_btc_xau import TP_SL_ADJUSTMENT_CONFIG, get_tp_sl_adjustment
from colorful_logger import print_info, print_success, print_error, print_warning

def test_scalping_normalization():
    """Test the SL×2.5 and TP×0.15 normalization for scalping"""
    
    print_info("Testing Scalping Normalization (SL×2.5, TP×0.15)")
    print_info("=" * 60)
    print_info("")
    print_info("Formula for both instruments:")
    print_info("  SL = DeepSeek SL × 2.5 (wide stops)")
    print_info("  TP = DeepSeek TP × 0.15 (tight profits)")
    print_info("")
    
    # Import the adjust_tp_sl function
    from bot_enhanced import adjust_tp_sl
    
    # Test cases
    test_cases = [
        {
            'name': 'XAUUSD BUY - Scalping',
            'symbol': 'XAUUSD',
            'entry': 2000.0,
            'deepseek_sl': 1990.0,  # 10 points away
            'deepseek_tp': 2020.0,  # 20 points away
            'expected_sl_distance': 10 * 2.5,  # 25
            'expected_tp_distance': 20 * 0.15,  # 3
            'direction': 'BUY'
        },
        {
            'name': 'XAUUSD SELL - Scalping',
            'symbol': 'XAUUSD',
            'entry': 2000.0,
            'deepseek_sl': 2010.0,  # 10 points away
            'deepseek_tp': 1980.0,  # 20 points away
            'expected_sl_distance': 10 * 2.5,  # 25
            'expected_tp_distance': 20 * 0.15,  # 3
            'direction': 'SELL'
        },
        {
            'name': 'BTCUSD BUY - Scalping',
            'symbol': 'BTCUSD',
            'entry': 100000.0,
            'deepseek_sl': 99500.0,  # 500 points away
            'deepseek_tp': 101000.0,  # 1000 points away
            'expected_sl_distance': 500 * 2.5,  # 1250
            'expected_tp_distance': 1000 * 0.15,  # 150
            'direction': 'BUY'
        },
        {
            'name': 'BTCUSD SELL - Scalping',
            'symbol': 'BTCUSD',
            'entry': 100000.0,
            'deepseek_sl': 100500.0,  # 500 points away
            'deepseek_tp': 99000.0,   # 1000 points away
            'expected_sl_distance': 500 * 2.5,  # 1250
            'expected_tp_distance': 1000 * 0.15,  # 150
            'direction': 'SELL'
        },
        {
            'name': 'Small movements - Gold',
            'symbol': 'XAUUSD',
            'entry': 2650.0,
            'deepseek_sl': 2645.0,  # 5 points away
            'deepseek_tp': 2660.0,  # 10 points away
            'expected_sl_distance': 5 * 2.5,  # 12.5
            'expected_tp_distance': 10 * 0.15,  # 1.5
            'direction': 'BUY'
        },
        {
            'name': 'Large movements - Bitcoin',
            'symbol': 'BTCUSD',
            'entry': 95000.0,
            'deepseek_sl': 94000.0,  # 1000 points away
            'deepseek_tp': 97000.0,  # 2000 points away
            'expected_sl_distance': 1000 * 2.5,  # 2500
            'expected_tp_distance': 2000 * 0.15,  # 300
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
        print_info(f"    SL Factor: ×{sl_factor}")
        print_info(f"    TP Factor: ×{tp_factor}")
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
        print_info(f"  Calculation: SL = {original_sl_distance:.2f} × 2.5 = {original_sl_distance * 2.5:.2f}")
        print_info(f"              TP = {original_tp_distance:.2f} × 0.15 = {original_tp_distance * 0.15:.2f}")
        
        # Display output
        print_info(f"  Final SL: {final_sl:.2f} (distance: {actual_sl_distance:.2f})")
        print_info(f"  Final TP: {final_tp:.2f} (distance: {actual_tp_distance:.2f})")
        
        # Check if calculations are correct (with tolerance for floating point)
        sl_correct = abs(actual_sl_distance - test['expected_sl_distance']) < 0.1
        tp_correct = abs(actual_tp_distance - test['expected_tp_distance']) < 0.1
        
        # Calculate Risk/Reward
        original_rr = original_tp_distance / original_sl_distance if original_sl_distance > 0 else 0
        final_rr = actual_tp_distance / actual_sl_distance if actual_sl_distance > 0 else 0
        
        if sl_correct and tp_correct:
            print_success(f"  [OK] Test passed!")
            print_info(f"  Original R:R: {original_rr:.2f}:1")
            print_info(f"  Final R:R: {final_rr:.3f}:1 (scalping ratio)")
            
            # Highlight the scalping nature
            if final_rr < 0.2:
                print_warning(f"  [!] Very tight profit target - requires {int(1/final_rr)} wins to break even after 1 loss")
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
        print_success("All tests passed! Scalping normalization working correctly.")
        print_info("")
        print_info("Summary:")
        print_info("  Both XAUUSD and BTCUSD now use:")
        print_info("    - SL = DeepSeek SL × 2.5 (increases stop loss by 150%)")
        print_info("    - TP = DeepSeek TP × 0.15 (reduces take profit by 85%)")
        print_info("    - Risk/Reward = 0.06 (requires ~17 wins per loss to profit)")
        print_info("")
        print_info("Strategy Characteristics:")
        print_info("  - Wide stops to avoid premature exits")
        print_info("  - Very tight profit targets for quick scalping")
        print_info("  - High win rate required (>94%) to be profitable")
        print_info("  - Suitable for high-frequency, high-probability setups")
        print_warning("")
        print_warning("  [!] WARNING: This is an extreme scalping configuration")
        print_warning("  [!] Requires very high win rate to be profitable")
        print_warning("  [!] Best suited for automated high-frequency trading")
    else:
        print_error("Some tests failed! Check the implementation.")

if __name__ == "__main__":
    test_scalping_normalization()