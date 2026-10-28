"""User preferences, stored as JSON in the per-user application data folder."""
import json
import os

from .messages import DEFAULT, SUPPORTED

SETTINGS_PATH = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
                             "MediaDownloader", "settings.json")


def _read():
    """Stored settings as a dict; a missing or unreadable file counts as no settings."""
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load_language():
    lang = _read().get("language")
    return lang if lang in SUPPORTED else DEFAULT


def save_language(lang):
    data = _read()
    data["language"] = lang
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
