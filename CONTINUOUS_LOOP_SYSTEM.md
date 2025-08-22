# Continuous Analyze-or-Monitor System

## Overview
The MT5 trading bot now operates in a **continuous loop** that analyzes pairs when no position exists, or monitors existing positions. The system processes pairs sequentially in a fixed order: XAUUSD first, then BTCUSD.

## Core Logic

### For Each Pair (in order):
1. **Check if position exists**
   - **YES**: Execute monitoring only (SL, TP, trailing, signal reversal)
   - **NO**: Perform full analysis and potentially open position

2. **Sequential Processing**
   - Always process XAUUSD first
   - Then process BTCUSD
   - Repeat continuously every 30-60 seconds

## Key Function: `analyze_or_monitor_pair()`

This function implements the core logic:

```python
def analyze_or_monitor_pair(symbol, account, blocked_pairs):
    positions = mt5.positions_get(symbol=symbol)
    
    if positions:
        # MONITOR EXISTING POSITION
        - Display position info (ticket, type, P/L)
        - Check SL elevation to breakeven
        - Manage trailing stops
        - Check for signal reversal
        return False  # No new position
    else:
        # ANALYZE FOR NEW POSITION
        - Check news blocks
        - Check trading hours
        - Calculate technical indicators
        - Get AI analysis
        - Open position if signal valid
        return True/False  # Position opened or not
```

## Execution Flow

### Each Cycle (every 30-60 seconds):

```
CYCLE START
├── Update cache & account info
├── Display position status
├── Check news blocks
│
├── [1/2] XAUUSD
│   ├── Has position? → MONITOR
│   │   ├── Check P/L
│   │   ├── Manage SL/TP
│   │   └── Check reversal
│   └── No position? → ANALYZE
│       ├── Technical analysis
│       ├── AI signal
│       └── Open if valid
│
├── [2/2] BTCUSD
│   ├── Has position? → MONITOR
│   │   ├── Check P/L
│   │   ├── Manage SL/TP
│   │   └── Check reversal
│   └── No position? → ANALYZE
│       ├── Technical analysis
│       ├── AI signal
│       └── Open if valid
│
└── CYCLE COMPLETE → Wait 30-60s → REPEAT
```

## Monitoring Features

When a position exists, the system:
1. **Displays** current P/L and position details
2. **Manages SL elevation** to breakeven + buffer
3. **Handles trailing stops** for profitable positions
4. **Checks signal reversals** to close if direction changes
5. **Maintains independent monitoring** per pair

## Analysis Features

When no position exists, the system:
1. **Checks blockers** (news, trading hours)
2. **Calculates indicators** (full technical analysis)
3. **Gets AI signal** (VOLVOLT-TRIAD strategy)
4. **Opens position** if confidence >= threshold
5. **Starts monitoring** immediately after opening

## Key Advantages

### 1. Efficient Resource Usage
- No unnecessary analysis when positions exist
- Quick monitoring checks for active positions
- Full analysis only when needed

### 2. Clear Separation
- Monitoring logic separate from analysis
- Each pair handled independently
- No cross-contamination between pairs

### 3. Continuous Operation
- Runs every 30-60 seconds
- Always processes in same order
- Predictable and consistent behavior

### 4. Independent Per Pair
- XAUUSD position doesn't affect BTCUSD analysis
- Each pair can have its own position
- Maximum 1 position per pair maintained

## Configuration

### Timing
- **Cycle interval**: 30-60 seconds (random)
- **Previous**: 1-2 minutes
- **Benefit**: More responsive to market changes

### Order
- **Fixed sequence**: XAUUSD → BTCUSD
- **Consistent**: Same order every cycle
- **Predictable**: Easy to track in logs

### Position Rules
- **Max per pair**: 1 position
- **Max total**: 2 positions (1 per pair)
- **Independence**: Each pair managed separately

## Example Scenarios

### Scenario 1: No Positions
```
Cycle 1: Analyze XAUUSD → Open BUY
         Analyze BTCUSD → No signal
Cycle 2: Monitor XAUUSD → Check P/L
         Analyze BTCUSD → Open SELL
Cycle 3: Monitor XAUUSD → Trailing stop
         Monitor BTCUSD → Check P/L
```

### Scenario 2: One Position
```
Cycle 1: Monitor XAUUSD (existing BUY)
         Analyze BTCUSD → Open SELL
Cycle 2: Monitor XAUUSD → Signal reversed → Close
         Monitor BTCUSD → Position maintained
Cycle 3: Analyze XAUUSD → New opportunity
         Monitor BTCUSD → Trailing activated
```

### Scenario 3: Both Positions
```
Cycle 1: Monitor XAUUSD → P/L check
         Monitor BTCUSD → P/L check
Cycle 2: Monitor XAUUSD → SL to breakeven
         Monitor BTCUSD → Position maintained
Cycle 3: Monitor XAUUSD → Trailing stop
         Monitor BTCUSD → Signal reversed → Close
```

## Log Output

The system provides clear logging:
```
═══ CYCLE #42 START ═══
POSITION STATUS
  • XAUUSD: {'action': 'BUY', 'confidence': 85.3}

SEQUENTIAL PAIR PROCESSING
═══ [1/2] XAUUSD ═══
[XAUUSD] MONITORING EXISTING POSITION
  Ticket: #123456 | Type: BUY
  P/L: $45.20 | Open: 14:32:15

═══ [2/2] BTCUSD ═══
[BTCUSD] ANALYZING FOR NEW POSITION
  Analyzing indicators...
  AI Signal: SELL (82.1%)
  Opening position...

CYCLE COMPLETE
  Active positions: 2/2
    • XAUUSD: Position active
    • BTCUSD: Position active
```

## Summary

The continuous analyze-or-monitor system provides:
- **Efficiency**: Only analyze when needed
- **Clarity**: Clear separation of concerns
- **Consistency**: Fixed processing order
- **Independence**: Each pair managed separately
- **Responsiveness**: 30-60 second cycles

This approach ensures optimal resource usage while maintaining constant market awareness and position management.