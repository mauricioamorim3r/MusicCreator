from __future__ import annotations

import json
from pathlib import Path

from core.dsp_engine import CHROMATIC
from services.config import knowledge_base_path
from services.models import MatchResult


def _camelot_compatible(query_key: str, candidate_key: str) -> tuple[bool, str]:
    if not query_key or not candidate_key or query_key == "N/A" or candidate_key == "N/A":
        return False, "sem dados"

    query_num = int(query_key[:-1])
    query_letter = query_key[-1]
    cand_num = int(candidate_key[:-1])
    cand_letter = candidate_key[-1]

    if query_key == candidate_key:
        return True, "match exato"
    if query_num == cand_num and query_letter != cand_letter:
        return True, "relativo maior/menor"
    if query_letter == cand_letter and cand_num in {((query_num - 2) % 12) + 1, (query_num % 12) + 1}:
        return True, "vizinho na roda Camelot"
    return False, "fora da zona ideal"


def _pitch_shift_semitones(query_note: str, candidate_note: str) -> int:
    if query_note not in CHROMATIC or candidate_note not in CHROMATIC:
        return 0
    delta = CHROMATIC.index(query_note) - CHROMATIC.index(candidate_note)
    if delta > 6:
        delta -= 12
    if delta < -6:
        delta += 12
    return int(delta)


def _medium_collision_risk(bpm_delta: float, pitch_shift: int, compatible: bool) -> str:
    if compatible and bpm_delta <= 2 and abs(pitch_shift) <= 1:
        return "baixo"
    if compatible and bpm_delta <= 5:
        return "medio"
    return "alto"


def find_mashup_candidates(dsp_payload: dict, limit: int = 5) -> MatchResult:
    catalog_path = knowledge_base_path("mashup_catalog.json")
    if not catalog_path.exists():
        return MatchResult(
            status="failure",
            error="Catálogo local de mashups não encontrado.",
            diagnostics=["Crie knowledge_base/mashup_catalog.json para habilitar o matcher."],
        )

    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    metrics = dsp_payload["acoustic_metrics"]
    query_bpm = float(metrics["bpm_measured"])
    query_key = metrics["camelot_key"]
    query_note = metrics["key_note"]

    scored = []
    for track in catalog.get("tracks", []):
        bpm_delta = abs(query_bpm - float(track["bpm"]))
        compatible, compatibility_reason = _camelot_compatible(query_key, track["camelot_key"])
        pitch_shift = _pitch_shift_semitones(query_note, track["key_note"])
        compatibility_score = round(
            max(0.0, 100.0 - (bpm_delta * 5.5) + (18.0 if compatible else -12.0) - (abs(pitch_shift) * 4.0)),
            1,
        )
        scored.append(
            {
                "title": track["title"],
                "artist": track["artist"],
                "genre": track.get("genre"),
                "bpm": track["bpm"],
                "camelot_key": track["camelot_key"],
                "pitch_shift_semitones": pitch_shift,
                "bpm_delta": round(bpm_delta, 1),
                "compatibility_reason": compatibility_reason,
                "compatibility_score": compatibility_score,
                "mid_collision_risk": _medium_collision_risk(bpm_delta, pitch_shift, compatible),
            }
        )

    candidates = sorted(scored, key=lambda item: item["compatibility_score"], reverse=True)[:limit]
    return MatchResult(
        status="success",
        mode="local_catalog",
        data={
            "query": {
                "bpm": query_bpm,
                "camelot_key": query_key,
                "key_note": query_note,
                "key_mode": metrics["key_mode"],
            },
            "candidates": candidates,
        },
        diagnostics=["Matcher local calculado com catálogo interno e heurística Camelot/BPM."],
        metadata={"catalog_path": str(Path(catalog_path).resolve())},
    )

