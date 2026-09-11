import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "data" / "site_config.json"


def load_site_config() -> dict:
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
