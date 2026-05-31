from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from services.config import (
    STEMS_CACHE_DIR,
    TRANSCRIPT_CACHE_DIR,
    ensure_runtime_dirs,
    premium_python_executable,
    premium_subprocess_env,
    premium_worker_path,
)
from services.models import StemResult, TranscriptResult


def _sha256_path(path: str | Path) -> str:
    hasher = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def separate_vocals(audio_path: str) -> StemResult:
    ensure_runtime_dirs()
    audio_hash = _sha256_path(audio_path)[:16]
    target_dir = STEMS_CACHE_DIR / audio_hash
    cached_vocals = target_dir / "vocals.wav"
    cached_mix = target_dir / "mix.wav"

    if cached_vocals.exists():
        return StemResult(
            status="success",
            mode="premium",
            data={
                "vocals_path": str(cached_vocals),
                "mix_path": str(cached_mix if cached_mix.exists() else Path(audio_path)),
                "stems": {"vocals": str(cached_vocals)},
            },
            diagnostics=["Stems reaproveitados do cache local."],
            metadata={"cache_hit": True},
        )

    runtime_python = premium_python_executable("demucs")
    if not runtime_python:
        return StemResult(
            status="success",
            mode="fallback",
            data={
                "vocals_path": audio_path,
                "mix_path": audio_path,
                "stems": {"full_mix": audio_path},
            },
            diagnostics=["Runtime Demucs ausente; usando a mix completa como fallback para análise vocal."],
            metadata={"cache_hit": False},
        )

    target_dir.mkdir(parents=True, exist_ok=True)
    command = [
        runtime_python,
        "-m",
        "demucs",
        "--two-stems",
        "vocals",
        "--device",
        "cpu",
        "-o",
        str(target_dir),
        audio_path,
    ]

    try:
        subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            env=premium_subprocess_env(runtime_python),
        )
        vocals_candidate = next(target_dir.rglob("vocals.wav"), None)
        no_vocals_candidate = next(target_dir.rglob("no_vocals.wav"), None)
        if vocals_candidate is None:
            raise FileNotFoundError("Demucs terminou sem produzir vocals.wav.")

        vocals_candidate.replace(cached_vocals)
        if no_vocals_candidate is not None:
            no_vocals_candidate.replace(cached_mix)

        return StemResult(
            status="success",
            mode="premium",
            data={
                "vocals_path": str(cached_vocals),
                "mix_path": str(cached_mix if cached_mix.exists() else Path(audio_path)),
                "stems": {
                    "vocals": str(cached_vocals),
                    "instrumental": str(cached_mix if cached_mix.exists() else Path(audio_path)),
                },
            },
            diagnostics=["Separação de vocais concluída com Demucs em CPU."],
            metadata={"cache_hit": False, "runtime_python": runtime_python},
        )
    except Exception as exc:
        return StemResult(
            status="success",
            mode="fallback",
            data={
                "vocals_path": audio_path,
                "mix_path": audio_path,
                "stems": {"full_mix": audio_path},
            },
            diagnostics=[f"Fallback acionado após falha do Demucs: {exc}"],
            metadata={"cache_hit": False, "runtime_python": runtime_python},
        )


def _empty_transcript() -> dict[str, Any]:
    return {"text": "", "language": None, "segments": [], "words": []}


def _has_transcript_text(transcript: dict[str, Any]) -> bool:
    if str(transcript.get("text") or "").strip():
        return True
    return any(str(segment.get("text") or "").strip() for segment in transcript.get("segments", []) or [])


def _normalize_cached_transcript(transcript: dict[str, Any]) -> dict[str, Any]:
    if not str(transcript.get("text") or "").strip() and transcript.get("segments"):
        transcript["text"] = "\n".join(
            str(segment.get("text") or "").strip()
            for segment in transcript.get("segments", [])
            if str(segment.get("text") or "").strip()
        ).strip()
    transcript.setdefault("alignment_status", "word_aligned" if transcript.get("words") else "segment_only")
    transcript.setdefault("transcription_confidence", "medium" if transcript.get("words") else "low")
    return transcript


def _save_transcript(path: Path, transcript: dict[str, Any]) -> None:
    path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_transcription_worker(vocals_path: str, transcript_path: Path) -> TranscriptResult:
    runtime_python = (
        premium_python_executable("whisperx")
        or premium_python_executable("whisper")
    )
    worker_path = premium_worker_path()
    if not runtime_python or not worker_path.exists():
        return TranscriptResult(
            status="success",
            mode="skipped",
            data=_empty_transcript(),
            diagnostics=["Runtime WhisperX/Whisper ausente; transcrição não executada."],
            metadata={"cache_hit": False},
        )

    worker_output = transcript_path.with_suffix(".worker.json")
    command = [
        runtime_python,
        str(worker_path),
        "transcribe",
        "--audio",
        vocals_path,
        "--output",
        str(worker_output),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            env=premium_subprocess_env(runtime_python),
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "worker sem diagnóstico").strip()
            raise RuntimeError(detail[-1200:])
        payload = json.loads(worker_output.read_text(encoding="utf-8"))
        transcript = _normalize_cached_transcript(payload.get("transcript") or _empty_transcript())
        mode = str(payload.get("mode") or "empty")
        diagnostics = [str(item) for item in payload.get("diagnostics", [])]
        if _has_transcript_text(transcript):
            _save_transcript(transcript_path, transcript)
        return TranscriptResult(
            status="success",
            mode=mode,
            data=transcript,
            diagnostics=diagnostics,
            metadata={
                "cache_hit": False,
                "transcript_path": str(transcript_path),
                "engine": str(payload.get("engine") or "premium_worker"),
                "runtime_python": runtime_python,
            },
        )
    except Exception as exc:
        return TranscriptResult(
            status="success",
            mode="skipped",
            data=_empty_transcript(),
            diagnostics=[f"Transcrição indisponível neste ambiente: {exc}"],
            metadata={"cache_hit": False, "runtime_python": runtime_python},
        )
    finally:
        worker_output.unlink(missing_ok=True)


def transcribe_vocals(vocals_path: str) -> TranscriptResult:
    ensure_runtime_dirs()
    transcript_hash = _sha256_path(vocals_path)[:16]
    transcript_path = TRANSCRIPT_CACHE_DIR / f"{transcript_hash}.json"

    if transcript_path.exists():
        transcript = _normalize_cached_transcript(json.loads(transcript_path.read_text(encoding="utf-8")))
        if _has_transcript_text(transcript):
            cached_mode = "premium" if transcript.get("alignment_status") == "word_aligned" else "rough"
            _save_transcript(transcript_path, transcript)
            return TranscriptResult(
                status="success",
                mode=cached_mode,
                data=transcript,
                diagnostics=["Transcrição reaproveitada do cache local."],
                metadata={"cache_hit": True, "transcript_path": str(transcript_path)},
            )

    return _run_transcription_worker(vocals_path, transcript_path)
