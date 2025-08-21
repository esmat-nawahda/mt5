# Fixed SL/TP Rules Implementation

## Overview
The trading bot now uses **FIXED** Stop Loss (SL) and Take Profit (TP) values for BTCUSD and XAUUSD, regardless of what DeepSeek AI suggests. The AI analysis is still used to determine trade direction (BUY/SELL) and confidence, but the SL/TP values are overridden with fixed pip values.

## Fixed Rules

### BTCUSD (Bitcoin)
- **BUY Position:**
  - SL = Entry Price - 240 pips
  - TP = Entry Price + 70 pips
  - Risk/Reward Ratio = 1:0.29

- **SELL Position:**
  - SL = Entry Price + 240 pips  
  - TP = Entry Price - 70 pips
  - Risk/Reward Ratio = 1:0.29

### XAUUSD (Gold)
- **BUY Position:**
  - SL = Entry Price - 500 pips (5.00 in price)
  - TP = Entry Price + 140 pips (1.40 in price)
  - Risk/Reward Ratio = 1:0.28

- **SELL Position:**
  - SL = Entry Price + 500 pips (5.00 in price)
  - TP = Entry Price - 140 pips (1.40 in price)
  - Risk/Reward Ratio = 1:0.28

## Implementation Details

### Files Modified

1. **bot_enhanced.py**
   - Modified `adjust_tp_sl()` function (lines 744-802)
   - Removed normalization and support/resistance logic
   - Implemented direct fixed pip calculations
   - Function now ignores DeepSeek's SL/TP suggestions and applies fixed values

2. **enhanced_config_btc_xau.py**
   - Set `use_normalization: False` (line 108)
   - Set `use_fixed_pips: True` (line 109)
   - Updated fixed pip values for both instruments (lines 126-129, 143-146)
   - Although configuration supports it, the actual implementation in bot_enhanced.py directly applies the rules

### How It Works

1. DeepSeek AI analyzes the market and provides:
   - Trade direction (BUY/SELL)
   - Confidence level
   - Entry price suggestion
   - SL/TP suggestions (which are now ignored)

2. The bot takes only the direction and confidence from AI

3. When placing a trade, the `adjust_tp_sl()` function:
   - Determines if it's a BUY or SELL based on AI's direction
   - Applies the fixed SL/TP rules based on the instrument
   - Returns the calculated SL/TP values

4. The trade is executed with these fixed values

### Testing

Run `test_fixed_sl_tp.py` to verify the implementation:
```bash
python test_fixed_sl_tp.py
```

This test script validates that the fixed rules are correctly applied for both instruments and both trade directions.

## Important Notes

- The Risk/Reward ratios are relatively low (around 1:0.28-0.29)
- These fixed values will be applied to ALL trades, regardless of market conditions
- The AI's market analysis is still used for trade timing and direction
- Consider monitoring performance and adjusting values if needed
- Ensure your account has sufficient margin for the larger stop losses

## Rollback Instructions

If you need to revert to the AI-suggested SL/TP values:

1. In `enhanced_config_btc_xau.py`:
   - Set `use_normalization: True`
   - Set `use_fixed_pips: False`

2. Restore the original `adjust_tp_sl()` function in `bot_enhanced.py` from backup

The bot will then use the normalization factors to adjust DeepSeek's suggestions instead of fixed values.