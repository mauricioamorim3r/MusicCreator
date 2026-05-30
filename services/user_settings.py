from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.config import CACHE_DIR, ensure_runtime_dirs
from services.local_database import load_setting, save_setting


SETTINGS_PATH = CACHE_DIR / "user_settings.json"


def load_user_settings() -> dict[str, Any]:
    ensure_runtime_dirs()
    db_settings = load_setting("user_settings", None)
    if isinstance(db_settings, dict):
        return db_settings
    if not SETTINGS_PATH.exists():
        return {}
    try:
        settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        if isinstance(settings, dict):
            save_setting("user_settings", settings)
        return settings
    except Exception:
        return {}


def save_user_settings(settings: dict[str, Any]) -> Path:
    ensure_runtime_dirs()
    save_setting("user_settings", settings)
    SETTINGS_PATH.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return SETTINGS_PATH
