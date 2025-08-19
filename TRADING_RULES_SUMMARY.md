# 📋 THANATOS-GUARDIAN-PRIME v15.2 TRADING RULES SUMMARY
## Complete Manual Review Checklist

---

## 🎯 TRADING INSTRUMENTS
- **ONLY TRADE:** XAUUSD (Gold) and BTCUSD (Bitcoin)
- **NO OTHER PAIRS ALLOWED**

## ⚠️ CRITICAL RULE: TP/SL REPLACEMENT
**EVERY DeepSeek suggestion is AUTOMATICALLY modified:**
- **BTCUSD:** SL multiplied by 4.7, TP multiplied by 0.15
- **XAUUSD:** SL multiplied by 1.8, TP multiplied by 0.40
- **This applies to ALL operations: new trades, updates, auto-refresh**

---

## ⚡ CORE ENTRY REQUIREMENTS (ALL MUST PASS)

### 1. **CONFIDENCE THRESHOLD**
- ✅ **Minimum:** 70% confidence required
- ⚠️ **Gold (XAUUSD):** Typically 70-85% (conservative)
- ⚠️ **Bitcoin (BTCUSD):** Can reach 85-95% (momentum-based)

### 2. **TECHNICAL INDICATORS (MANDATORY) - MORE TOLERANT ✅**
- ✅ **ADX > 15** - Confirms trend strength (reduced from 20)
- ✅ **ATR% ≥ 0.25%** - Minimum volatility required (reduced from 0.35%)
- ✅ **BB Width ≥ 0.4%** - Bollinger Bands expansion required (reduced from 0.6%)
- ❌ **Inside Lookback < 20** - No trade if last 20 H1 candles in consolidation (increased from 15)

### 3. **MULTI-TIMEFRAME ALIGNMENT**
- ✅ **H1 Trend:** Must be clear (Bullish/Bearish, not Sideways)
- ✅ **M15 Trend:** Should align with H1
- ✅ **M5 Setup:** Look for Breakout or Pullback patterns
- ✅ **MaxProtect Rule:** ACTIVE (TOLERANT MODE)
  - Allows up to 1 timeframe conflict
  - Only requires H1 and M15 alignment
  - M5 can diverge without blocking trades
  - Spread checks disabled

### 4. **VOLUME REQUIREMENTS**
- ✅ **Volume > MA50** on M5 timeframe
- ✅ **OBV Agreement** with price direction

---

## 🚫 BLOCKING CONDITIONS (ANY = NO TRADE)

### 1. **NEWS FILTER**
- ❌ **Block Window:** 45 minutes before/after high-impact USD news
- ❌ **News Types Blocked:** Red/High impact events only
- ✅ **Clear to trade:** When outside news windows

### 2. **POSITION LIMITS**
- ❌ **Max Concurrent Trades:** 2 (1 per instrument)
- ❌ **Max Daily Trades:** 20 total
- ❌ **Active Trades Check:** Skip analysis if already 2 positions open

### 3. **SPREAD LIMITS**
- ⚠️ **REMOVED FROM MAXPROTECT:** Spread no longer blocks trades
- ℹ️ **Note:** Spread monitoring available but not enforced

---

## 💰 RISK MANAGEMENT RULES

### 1. **POSITION SIZING**
- ⚠️ **REMOVED:** All position sizing constraints removed
- ⚠️ **REMOVED:** No automatic lot size calculations
- ✅ **Manual Control:** Trader has full control over lot sizes

### 2. **LOT SIZE LIMITS**
- ⚠️ **REMOVED:** All lot size limits removed
- ⚠️ **REMOVED:** No min/max lot restrictions
- ✅ **Broker Limits Only:** Only broker's natural limits apply

### 3. **TP/SL ADJUSTMENTS - EXTREME SCALPING MODE ⚠️⚠️⚠️**
| Instrument | TP Factor | SL Factor | Min RR | Min TP | Min SL | Max SL |
|------------|-----------|-----------|--------|--------|--------|--------|
| XAUUSD     | 0.40× (60% reduction) | 1.8× (80% increase) | 0.22 | 8 pts | 25 pts | 120 pts |
| BTCUSD     | 0.15× (85% reduction) | 4.7× (370% increase) | 0.03 | 15 pts | 250 pts | 1200 pts|

### 4. **STOP LOSS MANAGEMENT**
- ✅ **Automatic SL Placement:** If no SL exists, automatically places SL at breakeven when profit ≥ $50
- ✅ **SL to Breakeven:** Move existing SL to breakeven when profit ≥ $50
- ✅ **Breakeven Buffer:** +2 pips/points to avoid premature stops
- ⚡ **DYNAMIC TRAILING STOP:** Activates automatically when profit ≥ $60
- ✅ **Trail Distance:** 10 pips for ALL instruments (XAUUSD & BTCUSD)
- ✅ **Trail Step:** 1 pip minimum movement for precise tracking
- ✅ **Dynamic Mode:** Trails continuously as price moves in favor
- ✅ **Auto Check:** Every cycle monitors and adjusts
- ✅ **One-Way Movement:** SL only moves in favorable direction
- ✅ **Protection Level:** Keeps SL 10 pips behind current price

### 5. **AUTO-REFRESH SYSTEM** ⚡ NEW
- ✅ **Direction Change Detection:** Closes trade if DeepSeek signal reverses
- ✅ **SL/TP Auto-Update:** ALWAYS replaces DeepSeek values with:
  - **BTCUSD:** SL ×4.7 (+370%), TP ×0.15 (-85%)
  - **XAUUSD:** SL ×1.8 (+80%), TP ×0.40 (-60%)
- ✅ **Applied Everywhere:** New trades, position updates, auto-refresh
- ✅ **Smart Logging:** Shows DeepSeek values → Adjusted values
- ⚠️ **Example:** DeepSeek suggests SL:100 TP:50 → BTCUSD gets SL:470 TP:7.5

### 6. **EMERGENCY STOPS**
- ❌ **Max Drawdown:** 10% → Stop all trading
- ❌ **Consecutive Losses:** 5 → Pause 4 hours
- ❌ **Daily Loss Limit:** 5% → Stop for the day
- ❌ **Max Daily Risk:** 6% total exposure

---

## ⏰ SESSION WEIGHTS (CONFIDENCE ADJUSTMENTS)

| Session   | Time (CET)  | Weight | Effect on Confidence |
|-----------|-------------|--------|---------------------|
| Asian     | 00:00-08:00 | -2%    | Reduce confidence   |
| London    | 08:00-14:00 | +2%    | Boost confidence    |
| NY Open   | 14:00-17:00 | +3%    | Maximum boost       |
| NY Close  | 17:00-00:00 | 0%     | No adjustment       |

---

## 🔍 GUARDIAN FILTERS (ALL MUST PASS)

1. **Anti-Range Pass:** No extended consolidation detected (EXTREMELY TOLERANT) ✅
2. **Confluence Pass:** Multiple indicators align
3. **MaxProtect Pass:** TOLERANT - Allows 1 conflict, requires H1/M15 alignment ✅
4. **Session OK:** Trading in active session
5. **Structure OK:** H1/M15/M5 alignment confirmed
6. **Flow OK:** Volume and OBV agreement

✅ **MAXPROTECT ACTIVE:** Tolerant mode - allows 1 timeframe conflict, focuses on H1/M15 alignment

---

## 📊 INSTRUMENT-SPECIFIC RULES

### **XAUUSD (GOLD)**
- **Type:** Precious Metal, Safe Haven
- **Anti-Range Config:** Range ATR 0.85, Min candles 8, Compression 0.4 ✅ (MORE TOLERANT)
- **Analysis Focus:**
  - DXY inverse correlation (DXY ↑ = Gold ↓)
  - Psychological levels: 2000, 2050, 2100
  - Asian session accumulation patterns
  - Interest rate sensitivity
- **Trading Style:** Conservative, require strong confluence
- **Confidence Range:** 70-85% typical

### **BTCUSD (BITCOIN)**
- **Type:** Cryptocurrency, High Volatility
- **Anti-Range Config:** Range ATR 0.9, Min candles 6, Compression 0.3 ✅ (EXTREMELY TOLERANT)
- **Analysis Focus:**
  - Volume critical (low volume = false breakouts)
  - Weekend gaps common
  - Psychological levels: 100000, 95000, 90000
  - Tech stock correlation (NASDAQ)
- **Trading Style:** Momentum-based, aggressive on breakouts
- **Confidence Range:** Can reach 85-95% on strong setups

---

## 🔄 TRADE EXECUTION WORKFLOW

1. **Pre-Check Phase**
   - ✅ Check active positions (must be < 2)
   - ✅ Check news calendar
   - ✅ Verify spread acceptable

2. **Analysis Phase**
   - Calculate all technical indicators
   - Check multi-timeframe alignment
   - Apply instrument-specific analysis
   - Calculate confidence with session weights

3. **Validation Phase**
   - All 6 Guardian Filters must pass
   - Confidence must be ≥ 70%
   - Risk/Reward must meet minimums

4. **Execution Phase**
   - Calculate dynamic position size
   - Adjust TP/SL per instrument rules
   - Place order with slippage protection (3 pips)

---

## 📈 TRIPLE VALIDATION CHECKLIST

### ✅ **PASS 1: Technical**
- [ ] ADX > 20
- [ ] ATR% ≥ 0.35%
- [ ] BB Width ≥ 0.6%
- [ ] No 15-candle consolidation

### ✅ **PASS 2: Structure**
- [ ] H1 trend clear
- [ ] M15 aligned
- [ ] M5 setup valid
- [ ] Volume > MA50

### ✅ **PASS 3: Risk**
- [ ] No news blocking
- [ ] Spread acceptable
- [ ] Position limits OK
- [ ] R:R ratio meets minimum

---

## 🚨 WHEN NOT TO TRADE

1. **Time-Based:**
   - During high-impact news (±45 min)
   - After 5 consecutive losses (4hr pause)
   - When daily loss > 5%

2. **Market-Based:**
   - Range/consolidation > 20 H1 candles
   - Spread exceeds limits (removed from MaxProtect)
   - Volume < MA50
   - ✅ **Timeframe conflicts:** TOLERANT - Allows 1 conflict (H1/M15 must align)

3. **Account-Based:**
   - Already 2 positions open
   - Drawdown > 10%
   - Daily risk exposure > 6%
   - ⚠️ **Position sizing constraints removed**

---

## 📝 KEY NUMBERS TO REMEMBER

- **70%** - Minimum confidence threshold
- **15** - Minimum ADX value (reduced for tolerance)
- **0.25%** - Minimum ATR percentage (reduced for tolerance)
- **0.4%** - Minimum BB width percentage (reduced for tolerance)
- **20** - Max consolidation candles (increased for tolerance)
- **45** - Minutes news blocking window
- **2** - Maximum concurrent trades
- **20** - Maximum daily trades
- **$50** - SL to breakeven threshold ✅
- **$60** - Dynamic trailing stop activation ⚡
- **10** - Trailing distance in pips (all instruments) ✅
- **5s** - Maximum trade execution timeout ✅
- **10%** - Emergency stop drawdown
- **5** - Consecutive losses trigger

---

## ⚙️ SYSTEM CONFIGURATION

- **Check Interval:** 1-2 minutes (random) ⚡ FASTER SCANNING
- **API Timeout:** 60 seconds (with 2 retries)
- **Trade Execution:** 5 seconds maximum ✅
- **Magic Number:** 20250819
- **Slippage:** 3 pips maximum
- **Log Files:** `trade_journal.csv`, `prompt_log.json`

## ⚡ EXECUTION SPEED OPTIMIZATIONS ✅

1. **Pre-calculated Position Sizes**:
   - Cached every 30 seconds
   - No real-time calculation during execution
   - Instant lot size retrieval

2. **Fast Market Data**:
   - Spread info cached for 10 seconds
   - Bid/ask prices pre-fetched
   - No API calls during execution

3. **Optimized Order Flow**:
   - 5-second execution timeout
   - Maximum 2 retry attempts
   - Market orders for immediate execution
   - IOC (Immediate or Cancel) filling

4. **Smart Retry Logic**:
   - Auto-retry on requotes
   - Fresh price on retry
   - Brief pause between attempts
   - Execution time tracking

---

## 🎯 FINAL DECISION MATRIX

| Signal | Confidence | Guardian | News | Positions | ACTION |
|--------|------------|----------|------|-----------|---------|
| BUY/SELL | ≥70% | ALL PASS | CLEAR | <2 | ✅ EXECUTE |
| BUY/SELL | <70% | ANY | ANY | ANY | ❌ SKIP |
| BUY/SELL | ANY | ANY FAIL | ANY | ANY | ❌ SKIP |
| BUY/SELL | ANY | ANY | BLOCKED | ANY | ❌ SKIP |
| BUY/SELL | ANY | ANY | ANY | ≥2 | ❌ SKIP |
| NO_TRADE | ANY | ANY | ANY | ANY | ❌ SKIP |

**Note:** Spread column removed - spreads no longer block trade execution

---

## 🔔 IMPORTANT REMINDERS

1. **NEVER** trade without all Guardian Filters passing
2. **NEVER** exceed 2 concurrent positions
3. **ALWAYS** respect the news blocking window
4. **ALWAYS** use dynamic position sizing
5. **ALWAYS** adjust TP/SL per instrument rules
6. **STOP** immediately at 10% drawdown
7. **PAUSE** 4 hours after 5 consecutive losses
8. **LOG** every decision for review

---

*Last Updated: 2025-08-19*
*Protocol: Thanatos-Guardian-Prime v16.0-EXTREME-SCALPING*

---

## 🔄 RECENT CHANGES (Latest Updates)

### ✅ **2025-08-19 - CONFIGURATION UPDATES**

1. **Anti-Range Detection - MORE TOLERANT:**
   - **XAUUSD:** range_atr_ratio: 0.65 (was 0.5), min_candles: 6 (was 8), compression: 0.6 (was 0.8)
   - **BTCUSD:** range_atr_ratio: 0.75 (was 0.7), min_candles: 5 (was 12), compression: 0.5 (was 0.6)
   - **Result:** System now allows trading in previously blocked range conditions

2. **Position Sizing Constraints - REMOVED:**
   - **Removed:** All automatic position sizing calculations
   - **Removed:** Min/max lot size limits (0.01-2.0 for Gold, 0.01-0.5 for Bitcoin)
   - **Removed:** Position size percentages (1.5% Gold, 2.0% Bitcoin)
   - **Result:** Full manual control over lot sizes, no system restrictions

3. **MaxProtect Rule - REACTIVATED WITH TOLERANCE:**
   - **Active:** MaxProtect now checks timeframe alignment
   - **Tolerant:** Allows up to 1 timeframe conflict
   - **Focus:** H1 and M15 must align, M5 can diverge
   - **Spread:** Still not blocking trades
   - **Result:** More balanced approach between safety and opportunities

4. **TP/SL EXTREME ADJUSTMENT RULES - APPLIED TO ALL DEEPSEEK SUGGESTIONS:**
   - **XAUUSD:** TP ×0.40 (60% reduction), SL ×1.8 (80% increase)
   - **BTCUSD:** TP ×0.15 (85% reduction), SL ×4.7 (370% increase)
   - **Universal Application:** EVERY DeepSeek suggestion is modified by these factors
   - **Result:** Ultra-tight TPs with ultra-wide SLs for extreme scalping

5. **Automatic Stop Loss Protection:**
   - **NEW:** Automatically places SL at breakeven when profit reaches $50
   - **Safety:** Protects positions that were opened without stop loss
   - **Buffer:** Adds 2 pips/points buffer to avoid premature stops
   - **Result:** No position remains unprotected once profitable

6. **Dynamic Trailing Stop at $60:**
   - **NEW:** Activates dynamic trailing when profit reaches $60
   - **Trail Distance:** Fixed 10 pips for all instruments
   - **Precision:** 1-pip step size for smooth trailing
   - **Result:** Locks in profits while allowing upside potential