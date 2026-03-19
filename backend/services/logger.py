import json
from datetime import datetime
from pathlib import Path

LOG_FILE = Path(__file__).parent.parent / "logs.jsonl"

def log_event(event: dict):
    event["timestamp"] = datetime.now().isoformat()
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(event) + "\n")
