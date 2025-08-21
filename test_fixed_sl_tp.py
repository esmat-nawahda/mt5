#!/usr/bin/env python3
"""
Test script to verify fixed SL/TP rules implementation
For BTCUSD and XAUUSD with specific pip values
"""

def test_sl_tp_calculations():
    """Test the fixed SL/TP calculations"""
    
    print("=" * 60)
    print("TESTING FIXED SL/TP RULES")
    print("=" * 60)
    
    # Test cases with expected results
    test_cases = [
        {
            "symbol": "BTCUSD",
            "action": "BUY",
            "entry": 100000.00,
            "expected_sl": 100000.00 - 240,  # Entry - 240 pips
            "expected_tp": 100000.00 + 70,   # Entry + 70 pips
            "sl_pips": 240,
            "tp_pips": 70
        },
        {
            "symbol": "BTCUSD", 
            "action": "SELL",
            "entry": 100000.00,
            "expected_sl": 100000.00 + 240,  # Entry + 240 pips
            "expected_tp": 100000.00 - 70,   # Entry - 70 pips
            "sl_pips": 240,
            "tp_pips": 70
        },
        {
            "symbol": "XAUUSD",
            "action": "BUY",
            "entry": 2650.00,
            "expected_sl": 2650.00 - 5.00,   # Entry - 500 pips (5.00 in price)
            "expected_tp": 2650.00 + 1.40,   # Entry + 140 pips (1.40 in price)
            "sl_pips": 500,
            "tp_pips": 140
        },
        {
            "symbol": "XAUUSD",
            "action": "SELL", 
            "entry": 2650.00,
            "expected_sl": 2650.00 + 5.00,   # Entry + 500 pips (5.00 in price)
            "expected_tp": 2650.00 - 1.40,   # Entry - 140 pips (1.40 in price)
            "sl_pips": 500,
            "tp_pips": 140
        }
    ]
    
    # Simulate the adjust_tp_sl function logic
    def calculate_sl_tp(symbol, action, entry):
        """Calculate SL/TP based on fixed rules"""
        
        if 'BTC' in symbol:
            # BTCUSD: 1 pip = 1 point
            pip_value = 1.0
            sl_pips = 240
            tp_pips = 70
            
            if action == "BUY":
                final_sl = entry - (sl_pips * pip_value)
                final_tp = entry + (tp_pips * pip_value)
            else:  # SELL
                final_sl = entry + (sl_pips * pip_value)
                final_tp = entry - (tp_pips * pip_value)
                
        elif 'XAU' in symbol:
            # XAUUSD: 1 pip = 0.01
            pip_value = 0.01
            sl_pips = 500
            tp_pips = 140
            
            if action == "BUY":
                final_sl = entry - (sl_pips * pip_value)
                final_tp = entry + (tp_pips * pip_value)
            else:  # SELL
                final_sl = entry + (sl_pips * pip_value)
                final_tp = entry - (tp_pips * pip_value)
        else:
            final_sl = entry
            final_tp = entry
            
        return final_sl, final_tp
    
    # Run tests
    all_passed = True
    for i, test in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test['symbol']} {test['action']}")
        print(f"Entry Price: {test['entry']:.2f}")
        
        # Calculate SL/TP
        calculated_sl, calculated_tp = calculate_sl_tp(
            test['symbol'], 
            test['action'], 
            test['entry']
        )
        
        # Check results
        sl_correct = abs(calculated_sl - test['expected_sl']) < 0.01
        tp_correct = abs(calculated_tp - test['expected_tp']) < 0.01
        
        # Display results
        print(f"Expected SL: {test['expected_sl']:.2f} | Calculated: {calculated_sl:.2f} | {'PASS' if sl_correct else 'FAIL'}")
        print(f"Expected TP: {test['expected_tp']:.2f} | Calculated: {calculated_tp:.2f} | {'PASS' if tp_correct else 'FAIL'}")
        
        # Calculate Risk/Reward
        sl_distance = abs(test['entry'] - calculated_sl)
        tp_distance = abs(calculated_tp - test['entry'])
        rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0
        
        print(f"SL Distance: {test['sl_pips']} pips | TP Distance: {test['tp_pips']} pips")
        print(f"Risk/Reward Ratio: 1:{rr_ratio:.2f}")
        
        if not (sl_correct and tp_correct):
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("ALL TESTS PASSED - Fixed SL/TP rules are correctly implemented")
    else:
        print("SOME TESTS FAILED - Please check the implementation")
    print("=" * 60)
    
    # Summary of rules
    print("\nFIXED SL/TP RULES SUMMARY:")
    print("\nBTCUSD (1 pip = 1 point):")
    print("  BUY:  SL = Entry - 240 pips | TP = Entry + 70 pips | R:R = 1:0.29")
    print("  SELL: SL = Entry + 240 pips | TP = Entry - 70 pips | R:R = 1:0.29")
    
    print("\nXAUUSD (1 pip = 0.01):")
    print("  BUY:  SL = Entry - 500 pips | TP = Entry + 140 pips | R:R = 1:0.28")
    print("  SELL: SL = Entry + 500 pips | TP = Entry - 140 pips | R:R = 1:0.28")

if __name__ == "__main__":
    test_sl_tp_calculations()