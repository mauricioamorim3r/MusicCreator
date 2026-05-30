from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from services.config import DATABASE_PATH, ensure_runtime_dirs


SCHEMA_VERSION = 1


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    ensure_runtime_dirs()
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        initialize(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


def initialize(conn: sqlite3.Connection | None = None) -> None:
    owns_connection = conn is None
    if conn is None:
        ensure_runtime_dirs()
        conn = sqlite3.connect(DATABASE_PATH)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_runs (
                run_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                status TEXT,
                mode TEXT,
                source_type TEXT,
                source_title TEXT,
                source_artist TEXT,
                source_url TEXT,
                audio_path TEXT,
                llm_provider TEXT,
                llm_model TEXT,
                llm_effective_provider TEXT,
                llm_effective_model TEXT,
                llm_fallback_used INTEGER DEFAULT 0,
                enable_premium INTEGER DEFAULT 0,
                run_agents INTEGER DEFAULT 0,
                n_sections INTEGER,
                json_path TEXT,
                txt_path TEXT,
                stage_count INTEGER,
                total_elapsed_seconds REAL,
                slowest_stage TEXT,
                slowest_stage_seconds REAL,
                error TEXT,
                payload_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS generated_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                label TEXT NOT NULL,
                kind TEXT,
                path TEXT NOT NULL,
                mime TEXT,
                size_bytes INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES analysis_runs(run_id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            "INSERT OR REPLACE INTO app_meta(key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        if owns_connection:
            conn.commit()
    finally:
        if owns_connection:
            conn.close()


def load_setting(key: str, default: Any = None) -> Any:
    with connect() as conn:
        row = conn.execute("SELECT value_json FROM settings WHERE key = ?", (key,)).fetchone()
    if row is None:
        return default
    try:
        return json.loads(row["value_json"])
    except Exception:
        return default


def save_setting(key: str, value: Any) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO settings(key, value_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at = excluded.updated_at
            """,
            (key, json.dumps(value, ensure_ascii=False), datetime.now().astimezone().isoformat()),
        )


def save_analysis_run(entry: dict[str, Any], payload: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO analysis_runs(
                run_id, timestamp, status, mode, source_type, source_title, source_artist,
                source_url, audio_path, llm_provider, llm_model, llm_effective_provider,
                llm_effective_model, llm_fallback_used, enable_premium, run_agents,
                n_sections, json_path, txt_path, stage_count, total_elapsed_seconds,
                slowest_stage, slowest_stage_seconds, error, payload_json
            )
            VALUES (
                :run_id, :timestamp, :status, :mode, :source_type, :source_title,
                :source_artist, :source_url, :audio_path, :llm_provider, :llm_model,
                :llm_effective_provider, :llm_effective_model, :llm_fallback_used,
                :enable_premium, :run_agents, :n_sections, :json_path, :txt_path,
                :stage_count, :total_elapsed_seconds, :slowest_stage,
                :slowest_stage_seconds, :error, :payload_json
            )
            ON CONFLICT(run_id) DO UPDATE SET
                payload_json = excluded.payload_json,
                txt_path = excluded.txt_path,
                json_path = excluded.json_path,
                error = excluded.error
            """,
            {
                **entry,
                "llm_fallback_used": int(bool(entry.get("llm_fallback_used"))),
                "enable_premium": int(bool(entry.get("enable_premium"))),
                "run_agents": int(bool(entry.get("run_agents"))),
                "payload_json": json.dumps(payload, ensure_ascii=False, default=str),
            },
        )
        conn.execute("DELETE FROM generated_files WHERE run_id = ?", (entry["run_id"],))
        for item in _extract_generated_files(entry, payload):
            conn.execute(
                """
                INSERT INTO generated_files(run_id, label, kind, path, mime, size_bytes, created_at)
                VALUES (:run_id, :label, :kind, :path, :mime, :size_bytes, :created_at)
                """,
                item,
            )


def list_analysis_runs(limit: int = 30) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT run_id, timestamp, status, mode, source_type, source_title, source_artist,
                   source_url, audio_path, llm_provider, llm_model, llm_effective_provider,
                   llm_effective_model, llm_fallback_used, enable_premium, run_agents,
                   n_sections, json_path, txt_path, stage_count, total_elapsed_seconds,
                   slowest_stage, slowest_stage_seconds, error
            FROM analysis_runs
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_row_to_entry(row) for row in rows]


def load_analysis_run(run_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM analysis_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    if row is None:
        return None
    entry = _row_to_entry(row)
    try:
        payload = json.loads(row["payload_json"])
    except Exception:
        payload = {}
    return {"entry": entry, "payload": payload}


def _row_to_entry(row: sqlite3.Row) -> dict[str, Any]:
    entry = dict(row)
    entry.pop("payload_json", None)
    for key in ("llm_fallback_used", "enable_premium", "run_agents"):
        if key in entry:
            entry[key] = bool(entry[key])
    return entry


def _extract_generated_files(entry: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, Any]]:
    run_id = str(entry.get("run_id", ""))
    pipeline_data = payload.get("data", {}) or {}
    now = datetime.now().astimezone().isoformat()
    candidates: list[tuple[str, str, str, str]] = []

    source_path = ((pipeline_data.get("source") or {}).get("data") or {}).get("audio_path")
    if source_path:
        candidates.append(("Mix analisada", "audio", source_path, ""))

    stems_data = ((pipeline_data.get("stems") or {}).get("data") or {})
    stems = stems_data.get("stems", {}) or {}
    for label, key in (("Vocal separado", "vocals"), ("Instrumental", "instrumental"), ("Mix de fallback", "full_mix")):
        if stems.get(key):
            candidates.append((label, "audio", stems[key], ""))
    if stems_data.get("mix_path"):
        candidates.append(("Base sem vocal", "audio", stems_data["mix_path"], ""))

    transcript_path = ((pipeline_data.get("transcript") or {}).get("metadata") or {}).get("transcript_path")
    if transcript_path:
        candidates.append(("Transcrição JSON", "json", transcript_path, "application/json"))

    for label, path_key in (("Relatório JSON", "json_path"), ("Relatório TXT", "txt_path")):
        if entry_path := entry.get(path_key):
            candidates.append((label, "report", entry_path, ""))

    seen: set[str] = set()
    files: list[dict[str, Any]] = []
    for label, kind, raw_path, mime in candidates:
        path = str(raw_path)
        if not path or path in seen:
            continue
        seen.add(path)
        path_obj = Path(path)
        files.append(
            {
                "run_id": run_id,
                "label": label,
                "kind": kind,
                "path": path,
                "mime": mime,
                "size_bytes": path_obj.stat().st_size if path_obj.exists() else None,
                "created_at": now,
            }
        )
    return files
