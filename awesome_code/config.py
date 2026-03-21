import json
import os

CONFIG_DIR = os.path.expanduser("~/.awesome-code")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULTS = {
    "api_key": "",
    "model": "anthropic/claude-sonnet-4",
    "base_url": "https://openrouter.ai/api/v1",
}


def load() -> dict:
    if not os.path.exists(CONFIG_FILE):
        return dict(DEFAULTS)
    with open(CONFIG_FILE, "r") as f:
        data = json.load(f)
    return {**DEFAULTS, **data}


def save(config: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def is_configured() -> bool:
    cfg = load()
    return bool(cfg.get("api_key"))
