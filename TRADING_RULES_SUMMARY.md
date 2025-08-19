# 📋 THANATOS-GUARDIAN-PRIME v15.2 TRADING RULES SUMMARY
## Complete Manual Review Checklist

---

## 🎯 TRADING INSTRUMENTS
- **ONLY TRADE:** XAUUSD (Gold) and BTCUSD (Bitcoin)
- **NO OTHER PAIRS ALLOWED**

---

## ⚡ CORE ENTRY REQUIREMENTS (ALL MUST PASS)

### 1. **CONFIDENCE THRESHOLD**
- ✅ **Minimum:** 78% confidence required
- ⚠️ **Gold (XAUUSD):** Typically 78-85% (conservative)
- ⚠️ **Bitcoin (BTCUSD):** Can reach 85-95% (momentum-based)

### 2. **TECHNICAL INDICATORS (MANDATORY)**
- ✅ **ADX > 20** - Confirms trend strength
- ✅ **ATR% ≥ 0.35%** - Minimum volatility required
- ✅ **BB Width ≥ 0.6%** - Bollinger Bands expansion required
- ❌ **Inside Lookback < 15** - No trade if last 15 H1 candles in consolidation

### 3. **MULTI-TIMEFRAME ALIGNMENT**
- ✅ **H1 Trend:** Must be clear (Bullish/Bearish, not Sideways)
- ✅ **M15 Trend:** Should align with H1
- ✅ **M5 Setup:** Look for Breakout or Pullback patterns
- ❌ **MaxProtect Rule:** NO TRADE if ≥2 timeframes conflict

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

### 3. **TP/SL ADJUSTMENTS**
| Instrument | TP Factor | SL Factor | Min RR | Min TP | Min SL | Max SL |
|------------|-----------|-----------|--------|--------|--------|--------|
| XAUUSD     | 0.6×      | 1.1×      | 1.8    | 15 pts | 10 pts | 50 pts |
| BTCUSD     | 0.65×     | 1.15×     | 1.6    | 50 pts | 30 pts | 200 pts|

### 4. **STOP LOSS MANAGEMENT**
- ✅ **SL to Breakeven:** Move when profit ≥ $50
- ✅ **Breakeven Buffer:** +2 pips/points to avoid premature stops
- ✅ **Trailing Stop:** Activate after SL moved to breakeven
- ✅ **Trail Distance:** XAUUSD: 15 pips | BTCUSD: 40 points
- ✅ **Trail Step:** 5 pips/points minimum movement
- ✅ **Auto Check:** Every cycle monitors and adjusts
- ✅ **One-Way Movement:** SL only moves in favorable direction

### 5. **EMERGENCY STOPS**
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

1. **Anti-Range Pass:** No extended consolidation detected (MORE TOLERANT) ✅
2. **Confluence Pass:** Multiple indicators align
3. **MaxProtect Pass:** No timeframe conflicts
4. **Session OK:** Trading in active session
5. **Structure OK:** H1/M15/M5 alignment confirmed
6. **Flow OK:** Volume and OBV agreement

⚠️ **SPREAD REMOVED:** Spread limits no longer block trades in MaxProtect system

---

## 📊 INSTRUMENT-SPECIFIC RULES

### **XAUUSD (GOLD)**
- **Type:** Precious Metal, Safe Haven
- **Anti-Range Config:** Range ATR 0.65, Min candles 6, Compression 0.6 ✅
- **Analysis Focus:**
  - DXY inverse correlation (DXY ↑ = Gold ↓)
  - Psychological levels: 2000, 2050, 2100
  - Asian session accumulation patterns
  - Interest rate sensitivity
- **Trading Style:** Conservative, require strong confluence
- **Confidence Range:** 78-85% typical

### **BTCUSD (BITCOIN)**
- **Type:** Cryptocurrency, High Volatility
- **Anti-Range Config:** Range ATR 0.75, Min candles 5, Compression 0.5 ✅
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
   - Confidence must be ≥ 78%
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
   - Range/consolidation > 15 H1 candles
   - Spread exceeds limits
   - Volume < MA50
   - Timeframe conflicts (MaxProtect)

3. **Account-Based:**
   - Already 2 positions open
   - Drawdown > 10%
   - Daily risk exposure > 6%
   - ⚠️ **Position sizing constraints removed**

---

## 📝 KEY NUMBERS TO REMEMBER

- **78%** - Minimum confidence threshold
- **20** - Minimum ADX value
- **0.35%** - Minimum ATR percentage
- **0.6%** - Minimum BB width percentage
- **15** - Max consolidation candles
- **45** - Minutes news blocking window
- **2** - Maximum concurrent trades
- **20** - Maximum daily trades
- **$50** - SL elevation threshold (implemented) ✅
- **15/40** - Trailing distance (XAUUSD/BTCUSD pips/points) ✅
- **5s** - Maximum trade execution timeout ✅
- **10%** - Emergency stop drawdown
- **5** - Consecutive losses trigger

---

## ⚙️ SYSTEM CONFIGURATION

- **Check Interval:** 3-5 minutes (random)
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
| BUY/SELL | ≥78% | ALL PASS | CLEAR | <2 | ✅ EXECUTE |
| BUY/SELL | <78% | ANY | ANY | ANY | ❌ SKIP |
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
*Protocol: Thanatos-Guardian-Prime v15.3-TOLERANT-UNRESTRICTED*

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

3. **Spread Limits - REMOVED FROM MAXPROTECT:**
   - **Removed:** Spread blocking from Guardian Filters
   - **Result:** Trades no longer blocked by high spreads