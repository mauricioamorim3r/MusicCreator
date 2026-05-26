from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from services.config import CACHE_DIR, ensure_runtime_dirs


SETTINGS_PATH = CACHE_DIR / "user_settings.json"


def load_user_settings() -> dict[str, Any]:
    ensure_runtime_dirs()
    if not SETTINGS_PATH.exists():
        return {}
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_user_settings(settings: dict[str, Any]) -> Path:
    ensure_runtime_dirs()
    SETTINGS_PATH.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return SETTINGS_PATH
