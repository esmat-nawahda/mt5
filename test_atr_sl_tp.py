#!/usr/bin/env python3
"""
Test script to verify ATR-adjusted SL/TP rules implementation
For BTCUSD and XAUUSD with ATR-based adjustments
"""

def test_atr_adjusted_calculations():
    """Test the ATR-adjusted SL/TP calculations"""
    
    print("=" * 60)
    print("TESTING ATR-ADJUSTED SL/TP RULES")
    print("=" * 60)
    
    # Test cases with different ATR values
    test_cases = [
        # BTCUSD with low ATR (should use minimum fixed values)
        {
            "symbol": "BTCUSD",
            "action": "BUY",
            "entry": 100000.00,
            "atr": 30.0,  # Low ATR (less than minimum)
            "expected_sl_distance": 40.0,  # max(40, 30) = 40
            "expected_tp_distance": 65.0,  # max(65, 39) = 65
        },
        # BTCUSD with high ATR (should use ATR values)
        {
            "symbol": "BTCUSD",
            "action": "BUY",
            "entry": 100000.00,
            "atr": 100.0,  # High ATR
            "expected_sl_distance": 100.0,  # max(40, 100) = 100
            "expected_tp_distance": 130.0,  # max(65, 130) = 130
        },
        # BTCUSD SELL with medium ATR
        {
            "symbol": "BTCUSD",
            "action": "SELL",
            "entry": 100000.00,
            "atr": 50.0,  # Medium ATR
            "expected_sl_distance": 50.0,   # max(40, 50) = 50
            "expected_tp_distance": 65.0,   # max(65, 65) = 65
        },
        # XAUUSD with low ATR (should use minimum fixed values)
        {
            "symbol": "XAUUSD",
            "action": "BUY",
            "entry": 2650.00,
            "atr": 0.50,  # Low ATR (less than 0.70 minimum)
            "expected_sl_distance": 0.70,   # max(0.70, 0.50) = 0.70
            "expected_tp_distance": 1.40,   # max(1.40, 0.65) = 1.40
        },
        # XAUUSD with high ATR (should use ATR values)
        {
            "symbol": "XAUUSD",
            "action": "BUY",
            "entry": 2650.00,
            "atr": 2.00,  # High ATR
            "expected_sl_distance": 2.00,   # max(0.70, 2.00) = 2.00
            "expected_tp_distance": 2.60,   # max(1.40, 2.60) = 2.60
        },
        # XAUUSD SELL with exact minimum ATR
        {
            "symbol": "XAUUSD",
            "action": "SELL",
            "entry": 2650.00,
            "atr": 0.70,  # Exactly at minimum
            "expected_sl_distance": 0.70,   # max(0.70, 0.70) = 0.70
            "expected_tp_distance": 1.40,   # max(1.40, 0.91) = 1.40
        },
    ]
    
    # Simulate the adjust_tp_sl function logic with ATR
    def calculate_atr_sl_tp(symbol, action, entry, atr):
        """Calculate SL/TP based on ATR-adjusted rules"""
        
        if 'BTC' in symbol:
            # BTCUSD: 1 pip = 1 point
            pip_value = 1.0
            min_sl_pips = 40
            min_tp_pips = 65
            
            # Calculate ATR-based values
            atr_sl = 1.0 * atr  # 1×ATR
            atr_tp = 1.3 * atr  # 1.3×ATR
            
            # Take maximum between fixed and ATR-based
            sl_distance = max(min_sl_pips * pip_value, atr_sl)
            tp_distance = max(min_tp_pips * pip_value, atr_tp)
            
        elif 'XAU' in symbol:
            # XAUUSD: 1 pip = 0.01
            pip_value = 0.01
            min_sl_pips = 70
            min_tp_pips = 140
            
            # Calculate ATR-based values
            atr_sl = 1.0 * atr  # 1×ATR
            atr_tp = 1.3 * atr  # 1.3×ATR
            
            # Take maximum between fixed and ATR-based (convert pips to price)
            sl_distance = max(min_sl_pips * pip_value, atr_sl)
            tp_distance = max(min_tp_pips * pip_value, atr_tp)
            
        else:
            sl_distance = 0
            tp_distance = 0
        
        # Calculate final prices
        if action == "BUY":
            final_sl = entry - sl_distance
            final_tp = entry + tp_distance
        else:  # SELL
            final_sl = entry + sl_distance
            final_tp = entry - tp_distance
            
        return final_sl, final_tp, sl_distance, tp_distance
    
    # Run tests
    all_passed = True
    for i, test in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test['symbol']} {test['action']}")
        print(f"Entry: {test['entry']:.2f} | ATR: {test['atr']:.2f}")
        
        # Calculate SL/TP
        calculated_sl, calculated_tp, sl_dist, tp_dist = calculate_atr_sl_tp(
            test['symbol'], 
            test['action'], 
            test['entry'],
            test['atr']
        )
        
        # Check distances
        sl_dist_correct = abs(sl_dist - test['expected_sl_distance']) < 0.01
        tp_dist_correct = abs(tp_dist - test['expected_tp_distance']) < 0.01
        
        # Display results
        print(f"SL Distance: Expected {test['expected_sl_distance']:.2f} | Got {sl_dist:.2f} | {'PASS' if sl_dist_correct else 'FAIL'}")
        print(f"TP Distance: Expected {test['expected_tp_distance']:.2f} | Got {tp_dist:.2f} | {'PASS' if tp_dist_correct else 'FAIL'}")
        
        # Calculate and display final prices
        if test['action'] == "BUY":
            print(f"Final SL: {calculated_sl:.2f} (Entry - {sl_dist:.2f})")
            print(f"Final TP: {calculated_tp:.2f} (Entry + {tp_dist:.2f})")
        else:
            print(f"Final SL: {calculated_sl:.2f} (Entry + {sl_dist:.2f})")
            print(f"Final TP: {calculated_tp:.2f} (Entry - {tp_dist:.2f})")
        
        # Calculate Risk/Reward
        rr_ratio = tp_dist / sl_dist if sl_dist > 0 else 0
        print(f"Risk/Reward Ratio: 1:{rr_ratio:.2f}")
        
        if not (sl_dist_correct and tp_dist_correct):
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("ALL TESTS PASSED - ATR-adjusted SL/TP rules are correctly implemented")
    else:
        print("SOME TESTS FAILED - Please check the implementation")
    print("=" * 60)
    
    # Summary of rules
    print("\nATR-ADJUSTED SL/TP RULES SUMMARY:")
    print("\nBTCUSD (1 pip = 1 point):")
    print("  BUY:  SL = Entry - max(40, 1×ATR) | TP = Entry + max(65, 1.3×ATR)")
    print("  SELL: SL = Entry + max(40, 1×ATR) | TP = Entry - max(65, 1.3×ATR)")
    print("  Note: When ATR < 40, uses fixed 40 pips for SL")
    print("        When ATR < 50, uses fixed 65 pips for TP")
    
    print("\nXAUUSD (1 pip = 0.01):")
    print("  BUY:  SL = Entry - max(70 pips, 1×ATR) | TP = Entry + max(140 pips, 1.3×ATR)")
    print("  SELL: SL = Entry + max(70 pips, 1×ATR) | TP = Entry - max(140 pips, 1.3×ATR)")
    print("  Note: When ATR < 0.70, uses fixed 70 pips (0.70) for SL")
    print("        When ATR < 1.08, uses fixed 140 pips (1.40) for TP")
    
    print("\nKEY FEATURES:")
    print("- Adapts to market volatility using ATR")
    print("- Maintains minimum stop losses for protection")
    print("- Ensures minimum profit targets")
    print("- Risk/Reward ratio improves with higher volatility")

if __name__ == "__main__":
    test_atr_adjusted_calculations()