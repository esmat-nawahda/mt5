import csv
import os
import json
from datetime import datetime

LOG_FILE = os.getenv("TRADE_LOG_FILE", "trade_journal.csv")
PROMPT_LOG_FILE = os.getenv("PROMPT_LOG_FILE", "prompt_log.json")

def init_logger():
    if not os.path.isfile(LOG_FILE):
        with open(LOG_FILE, mode="w", newline="") as f:
            w = csv.writer(f)
            w.writerow([
                "timestamp","trade_id","pair","action","confidence",
                "entry_price","sl","tp","status","reason","pnl","win_loss"
            ])
    
    if not os.path.isfile(PROMPT_LOG_FILE):
        with open(PROMPT_LOG_FILE, mode="w") as f:
            json.dump([], f)

def log_trade(trade_id, pair, action, confidence, entry_price, sl, tp,
              status="OPEN", reason="", pnl="", win_loss=""):
    with open(LOG_FILE, mode="a", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            trade_id, pair, action, confidence,
            entry_price, sl, tp, status, reason, pnl, win_loss
        ])

def log_analysis_prompt(symbol, prompt, checked_rules, ai_response):
    """Log the full prompt and all checked rules for each analysis"""
    try:
        # Convert numpy/pandas types to native Python types for JSON serialization
        def convert_to_serializable(obj):
            if isinstance(obj, dict):
                return {k: convert_to_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_serializable(item) for item in obj]
            elif hasattr(obj, 'item'):  # numpy types
                return obj.item()
            elif hasattr(obj, 'tolist'):  # numpy arrays
                return obj.tolist()
            elif isinstance(obj, (bool, int, float, str, type(None))):
                return obj
            else:
                return str(obj)
        
        # Load existing logs with better error handling
        logs = []
        if os.path.isfile(PROMPT_LOG_FILE):
            try:
                with open(PROMPT_LOG_FILE, "r") as f:
                    content = f.read()
                    if content.strip():  # Only parse if file is not empty
                        logs = json.loads(content)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not read existing prompt log, creating new: {e}")
                logs = []
        
        # Extract key decision data from AI response
        ai_response_serializable = convert_to_serializable(ai_response)
        decision_summary = {
            "action": ai_response_serializable.get("action", "NO_TRADE"),
            "confidence": ai_response_serializable.get("confidence", 0),
            "confidence_breakdown": ai_response_serializable.get("confidence_breakdown", {}),
            "entry": ai_response_serializable.get("entry"),
            "sl": ai_response_serializable.get("sl"),
            "tp1": ai_response_serializable.get("tp1"),
            "tp2": ai_response_serializable.get("tp2"),
            "tp3": ai_response_serializable.get("tp3"),
            "analysis": ai_response_serializable.get("analysis", ""),
            "guardian_status": ai_response_serializable.get("guardian_status", {})
        }
        
        # Add new log entry with conversion
        log_entry = {
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "decision_summary": decision_summary,
            "prompt": prompt,
            "checked_rules": convert_to_serializable(checked_rules),
            "ai_response": ai_response_serializable
        }
        logs.append(log_entry)
        
        # Keep only last 100 entries to prevent file from growing too large
        if len(logs) > 100:
            logs = logs[-100:]
        
        # Write back to file
        with open(PROMPT_LOG_FILE, "w") as f:
            json.dump(logs, f, indent=2, default=str)  # Added default=str as fallback
    except Exception as e:
        print(f"Failed to log prompt: {e}")
        import traceback
        traceback.print_exc()
