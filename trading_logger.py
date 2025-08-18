import csv
import os
from datetime import datetime

LOG_FILE = os.getenv("TRADE_LOG_FILE", "trade_journal.csv")

def init_logger():
    if not os.path.isfile(LOG_FILE):
        with open(LOG_FILE, mode="w", newline="") as f:
            w = csv.writer(f)
            w.writerow([
                "timestamp","trade_id","pair","action","confidence",
                "entry_price","sl","tp","status","reason","pnl","win_loss"
            ])

def log_trade(trade_id, pair, action, confidence, entry_price, sl, tp,
              status="OPEN", reason="", pnl="", win_loss=""):
    with open(LOG_FILE, mode="a", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            trade_id, pair, action, confidence,
            entry_price, sl, tp, status, reason, pnl, win_loss
        ])
