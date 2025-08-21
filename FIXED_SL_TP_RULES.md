# ATR-Adjusted SL/TP Rules Implementation

## Overview
The trading bot now uses **ATR-ADJUSTED** Stop Loss (SL) and Take Profit (TP) values that adapt to market volatility while maintaining minimum protective levels. The AI analysis is still used to determine trade direction (BUY/SELL) and confidence, but the SL/TP values are calculated using ATR (Average True Range) with minimum fixed values as a floor.

## ATR-Adjusted Rules

### BTCUSD (Bitcoin)
- **BUY Position:**
  - SL = Entry Price - max(40 pips, 1×ATR)
  - TP = Entry Price + max(65 pips, 1.5×ATR)
  - Minimum Risk/Reward Ratio = 1:1.5 (up to 1:1.62 with low volatility)

- **SELL Position:**
  - SL = Entry Price + max(40 pips, 1×ATR)
  - TP = Entry Price - max(65 pips, 1.5×ATR)
  - Minimum Risk/Reward Ratio = 1:1.5 (up to 1:1.62 with low volatility)

### XAUUSD (Gold)
- **BUY Position:**
  - SL = Entry Price - max(70 pips, 1×ATR) 
  - TP = Entry Price + max(140 pips, 1.5×ATR)
  - Minimum Risk/Reward Ratio = 1:1.5 (up to 1:2.0 with low volatility)

- **SELL Position:**
  - SL = Entry Price + max(70 pips, 1×ATR)
  - TP = Entry Price - max(140 pips, 1.5×ATR)
  - Minimum Risk/Reward Ratio = 1:1.5 (up to 1:2.0 with low volatility)

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

### How ATR Adjustment Works

1. **ATR Calculation**: The bot calculates the 14-period ATR on H1 timeframe
2. **Minimum Values**: Each instrument has minimum SL/TP distances that act as a floor
3. **Maximum Function**: The bot takes the MAXIMUM between:
   - The minimum fixed pip value
   - The ATR-based calculation (1×ATR for SL, 1.5×ATR for TP)
4. **Dynamic Adaptation**: 
   - In low volatility: Uses minimum fixed values for protection
   - In high volatility: Uses larger ATR-based values for wider stops

### Testing

Run `test_atr_sl_tp.py` to verify the implementation:
```bash
python test_atr_sl_tp.py
```

This test script validates the ATR-adjusted calculations with various volatility scenarios.

## Important Notes

- **Adaptive to Volatility**: Automatically widens stops in volatile markets
- **Protected Minimums**: Never goes below minimum safety thresholds
- **Excellent Risk/Reward**: Maintains minimum 1:1.5 ratio, often better
- **ATR Source**: Uses H1 timeframe ATR(14) for consistency
- **Volatility Thresholds**:
  - BTCUSD: ATR < 40 uses fixed minimums
  - XAUUSD: ATR < 0.70 uses fixed minimums
- **Benefits**:
  - Reduces stop-outs in volatile conditions
  - Maintains tight stops in calm markets
  - Adapts to changing market conditions automatically

## Rollback Instructions

If you need to revert to the AI-suggested SL/TP values:

1. In `enhanced_config_btc_xau.py`:
   - Set `use_normalization: True`
   - Set `use_fixed_pips: False`

2. Restore the original `adjust_tp_sl()` function in `bot_enhanced.py` from backup

The bot will then use the normalization factors to adjust DeepSeek's suggestions instead of fixed values.