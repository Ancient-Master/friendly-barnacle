import json
import os

CONFIG_FILE = "config.json"

default_config = {
    "target_name": "",
    "server": "Normal",
    "job_id": "",
    "send_webhook": False,
    "mention_choice": "0",
    "enable_shutdown": False,
    "monitors": [1]   # Standard: nur Hauptmonitor
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(default_config)
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        save_config(default_config)
        return default_config

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)
