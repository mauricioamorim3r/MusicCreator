from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from services.config import STEMS_CACHE_DIR, TRANSCRIPT_CACHE_DIR, ensure_runtime_dirs, optional_dependency_available
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

    if not optional_dependency_available("demucs"):
        return StemResult(
            status="success",
            mode="fallback",
            data={
                "vocals_path": audio_path,
                "mix_path": audio_path,
                "stems": {"full_mix": audio_path},
            },
            diagnostics=["Demucs ausente; usando a mix completa como fallback para análise vocal."],
            metadata={"cache_hit": False},
        )

    target_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
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
        subprocess.run(command, capture_output=True, text=True, check=True)
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
            metadata={"cache_hit": False},
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
            metadata={"cache_hit": False},
        )


def _serialize_transcript(result: dict[str, Any]) -> dict[str, Any]:
    segments = []
    words = []
    for segment in result.get("segments", []):
        segment_text = segment.get("text", "").strip()
        if not segment_text:
            continue
        segments.append(
            {
                "start": float(segment.get("start", 0.0)),
                "end": float(segment.get("end", 0.0)),
                "text": segment_text,
            }
        )
        for word in segment.get("words", []) or []:
            word_text = word.get("word", "").strip()
            if not word_text:
                continue
            words.append(
                {
                    "word": word_text,
                    "start": float(word.get("start", 0.0)),
                    "end": float(word.get("end", 0.0)),
                    "score": float(word.get("score", 0.0)),
                }
            )
    text = result.get("text", "").strip()
    if not text and segments:
        text = "\n".join(segment["text"] for segment in segments).strip()
    return {
        "text": text,
        "language": result.get("language"),
        "segments": segments,
        "words": words,
    }


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


def _transcribe_with_openai_whisper(vocals_path: str, transcript_path: Path) -> TranscriptResult | None:
    if not optional_dependency_available("whisper"):
        return None

    try:
        import whisper

        model = whisper.load_model("base", device="cpu")
        result = model.transcribe(vocals_path, fp16=False, verbose=False)
        transcript = _serialize_transcript(result)
        transcript["alignment_status"] = "not_aligned"
        transcript["transcription_confidence"] = "low" if _has_transcript_text(transcript) else "none"
        if _has_transcript_text(transcript):
            _save_transcript(transcript_path, transcript)
            return TranscriptResult(
                status="success",
                mode="rough",
                data=transcript,
                diagnostics=[
                    "Transcrição bruta gerada com Whisper sem alinhamento por palavra. Revise antes de usar como letra final."
                ],
                metadata={"cache_hit": False, "transcript_path": str(transcript_path), "engine": "openai_whisper"},
            )
        return TranscriptResult(
            status="success",
            mode="empty",
            data=transcript,
            diagnostics=["Whisper executou, mas não encontrou texto vocal utilizável no áudio."],
            metadata={"cache_hit": False, "engine": "openai_whisper"},
        )
    except Exception:
        return None


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

    if not optional_dependency_available("whisperx"):
        whisper_result = _transcribe_with_openai_whisper(vocals_path, transcript_path)
        if whisper_result is not None:
            return whisper_result
        return TranscriptResult(
            status="success",
            mode="skipped",
            data=_empty_transcript(),
            diagnostics=["WhisperX ausente e fallback Whisper indisponível; transcrição não executada."],
            metadata={"cache_hit": False},
        )

    try:
        import whisperx

        device = "cpu"
        compute_type = "int8"
        batch_size = 4
        audio = whisperx.load_audio(vocals_path)
        model = whisperx.load_model("small", device=device, compute_type=compute_type)
        result = model.transcribe(audio, batch_size=batch_size)

        language_code = result.get("language") or "en"
        base_transcript = _serialize_transcript(
            {
                "text": result.get("text", ""),
                "language": language_code,
                "segments": result.get("segments", []),
            }
        )
        base_transcript["alignment_status"] = "not_aligned"
        base_transcript["transcription_confidence"] = "low" if _has_transcript_text(base_transcript) else "none"

        if not _has_transcript_text(base_transcript):
            return TranscriptResult(
                status="success",
                mode="empty",
                data=base_transcript,
                diagnostics=["WhisperX executou, mas não encontrou texto vocal utilizável no áudio."],
                metadata={"cache_hit": False, "engine": "whisperx"},
            )

        try:
            align_model, metadata = whisperx.load_align_model(language_code=language_code, device=device)
            aligned = whisperx.align(
                result["segments"],
                align_model,
                metadata,
                audio,
                device,
                return_char_alignments=False,
            )
            transcript = _serialize_transcript(
                {
                    "text": base_transcript["text"],
                    "language": language_code,
                    "segments": aligned.get("segments", []),
                }
            )
            if not _has_transcript_text(transcript):
                transcript = base_transcript
            transcript["alignment_status"] = "word_aligned" if transcript.get("words") else "segment_only"
            transcript["transcription_confidence"] = "medium" if transcript.get("words") else "low"
            _save_transcript(transcript_path, transcript)

            return TranscriptResult(
                status="success",
                mode="premium" if transcript.get("words") else "rough",
                data=transcript,
                diagnostics=[
                    "WhisperX executado com alinhamento em nível de palavra."
                    if transcript.get("words")
                    else "WhisperX gerou texto, mas sem palavras alinhadas. Entregando transcrição bruta por segmento."
                ],
                metadata={"cache_hit": False, "transcript_path": str(transcript_path), "engine": "whisperx"},
            )
        except Exception as align_exc:
            _save_transcript(transcript_path, base_transcript)
            return TranscriptResult(
                status="success",
                mode="rough",
                data=base_transcript,
                diagnostics=[
                    "WhisperX gerou texto, mas o alinhamento falhou. Entregando transcrição bruta.",
                    f"Falha no alinhamento: {align_exc}",
                ],
                metadata={"cache_hit": False, "transcript_path": str(transcript_path), "engine": "whisperx"},
            )

    except Exception as exc:
        whisper_result = _transcribe_with_openai_whisper(vocals_path, transcript_path)
        if whisper_result is not None:
            whisper_result.diagnostics.insert(
                0,
                f"WhisperX falhou; fallback Whisper acionado: {exc}",
            )
            return whisper_result
        return TranscriptResult(
            status="success",
            mode="skipped",
            data=_empty_transcript(),
            diagnostics=[f"Transcrição indisponível neste ambiente: {exc}"],
            metadata={"cache_hit": False},
        )
