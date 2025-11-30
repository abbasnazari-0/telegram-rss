import json
from pathlib import Path

CONFIG_FILE = Path("config.json")

def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return None

def save_config(api_id, api_hash, phone):
    data = {
        "API_ID": api_id,
        "API_HASH": api_hash,
        "PHONE": phone
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)
