from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from services.config import CACHE_DIR, ensure_runtime_dirs
from services.local_database import list_analysis_runs, load_analysis_run, save_analysis_run


HISTORY_DIR = CACHE_DIR / "history"
HISTORY_INDEX_PATH = HISTORY_DIR / "history_index.json"


def _safe_slug(value: str, default: str = "analysis") -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in (value or "").strip())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return (cleaned or default)[:48]


def _load_history_index() -> list[dict[str, Any]]:
    ensure_runtime_dirs()
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    if not HISTORY_INDEX_PATH.exists():
        return []
    try:
        return json.loads(HISTORY_INDEX_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _migrate_json_history_to_database() -> None:
    for entry in _load_history_index():
        run_id = entry.get("run_id")
        json_path = Path(str(entry.get("json_path", "")))
        if not run_id or not json_path.exists():
            continue
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        save_analysis_run(entry, payload)


def _save_history_index(entries: list[dict[str, Any]]) -> None:
    HISTORY_INDEX_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def persist_analysis_run(result_payload: dict[str, Any]) -> dict[str, Any]:
    ensure_runtime_dirs()
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().astimezone().isoformat()
    run_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
    pipeline_data = result_payload.get("data", {}) or {}
    source = pipeline_data.get("source", {}) or {}
    source_data = source.get("data", {}) or {}
    source_title = source_data.get("title") or source_data.get("source_name") or "analysis"
    source_kind = source_data.get("source_type") or "unknown"
    report_slug = _safe_slug(f"{source_kind}_{source_title}")

    json_path = HISTORY_DIR / f"{run_id}_{report_slug}.json"
    json_path.write_text(json.dumps(result_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    txt_path: Path | None = None
    text_report = pipeline_data.get("text_report")
    if isinstance(text_report, str) and text_report.strip():
        txt_path = HISTORY_DIR / f"{run_id}_{report_slug}.txt"
        txt_path.write_text(text_report, encoding="utf-8")

    stage_log = pipeline_data.get("stage_log", []) or result_payload.get("metadata", {}).get("stage_log", []) or []
    analysis_context = pipeline_data.get("analysis_context", {}) or {}
    performance = pipeline_data.get("performance", {}) or result_payload.get("metadata", {}).get("performance", {}) or {}
    agents_metadata = ((pipeline_data.get("agents") or {}).get("metadata") or {})
    entry = {
        "run_id": run_id,
        "timestamp": timestamp,
        "status": result_payload.get("status"),
        "mode": result_payload.get("mode"),
        "source_type": source_kind,
        "source_title": source_title,
        "source_artist": source_data.get("artist", ""),
        "source_url": source_data.get("source_url", ""),
        "audio_path": source_data.get("audio_path", ""),
        "llm_provider": analysis_context.get("llm_provider", ""),
        "llm_model": analysis_context.get("llm_model", ""),
        "llm_effective_provider": agents_metadata.get("llm_provider", ""),
        "llm_effective_model": agents_metadata.get("llm_model", ""),
        "llm_fallback_used": bool(agents_metadata.get("llm_fallback_used", False)),
        "enable_premium": bool(analysis_context.get("enable_premium", False)),
        "run_agents": bool(analysis_context.get("run_agents", False)),
        "n_sections": analysis_context.get("n_sections"),
        "json_path": str(json_path),
        "txt_path": str(txt_path) if txt_path else "",
        "stage_count": len(stage_log),
        "total_elapsed_seconds": performance.get("total_elapsed_seconds"),
        "slowest_stage": performance.get("slowest_stage", ""),
        "slowest_stage_seconds": performance.get("slowest_stage_seconds"),
        "error": result_payload.get("error", ""),
    }

    entries = _load_history_index()
    entries.insert(0, entry)
    _save_history_index(entries[:100])
    save_analysis_run(entry, result_payload)
    return entry


def load_analysis_history(limit: int = 30) -> list[dict[str, Any]]:
    entries = list_analysis_runs(limit=limit)
    if entries:
        return entries
    _migrate_json_history_to_database()
    entries = list_analysis_runs(limit=limit)
    return entries or _load_history_index()[:limit]


def load_history_run(run_id: str) -> dict[str, Any] | None:
    loaded = load_analysis_run(run_id)
    if loaded:
        return loaded
    for entry in _load_history_index():
        if entry.get("run_id") != run_id:
            continue
        json_path = Path(str(entry.get("json_path", "")))
        if not json_path.exists():
            return None
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return {"entry": entry, "payload": payload}
    return None
