from __future__ import annotations

from typing import Any

from services.audio_pipeline import analyze_audio_cached, ingest_uploaded_audio
from services.loudness_analyzer import analyze_loudness
from services.vocals_processor import separate_vocals, transcribe_vocals


MAX_TRANSCRIPT_CHARS = 12_000
MAX_TRANSCRIPT_SEGMENTS = 40


def build_audio_attachment_dossier(
    name: str,
    content: bytes,
    *,
    enable_premium: bool = False,
    n_sections: int = 8,
) -> dict[str, Any]:
    """Build a provider-neutral audio dossier for a Copilot attachment."""
    ingest = ingest_uploaded_audio(name, content)
    if not ingest.ok:
        return {
            "status": "failure",
            "diagnostics": ingest.diagnostics,
            "error": ingest.error or "Não foi possível preparar o áudio anexado.",
        }

    audio_path = str(ingest.data["audio_path"])
    try:
        dsp = analyze_audio_cached(audio_path, n_sections=n_sections)
    except Exception as exc:
        return {
            "status": "failure",
            "source": _public_source(ingest.to_dict()),
            "diagnostics": [f"Falha na leitura DSP do anexo: {exc}"],
            "error": str(exc),
        }

    loudness = analyze_loudness(audio_path)
    dossier: dict[str, Any] = {
        "status": "success",
        "analysis_mode": "local_dsp",
        "_audio_path": audio_path,
        "source": _public_source(ingest.to_dict()),
        "dsp": _public_dsp(dsp.to_dict()),
        "loudness": _public_envelope(loudness.to_dict()),
        "premium_requested": enable_premium,
        "diagnostics": [
            "Dossiê local do anexo pronto. As próximas perguntas reaproveitam o cache DSP.",
        ],
    }

    if not enable_premium:
        dossier["premium"] = {
            "status": "skipped",
            "message": (
                "Leitura aprofundada de voz desativada para este anexo. "
                "Ative a opção premium do Copiloto para tentar separar vocal e transcrever."
            ),
        }
        return dossier

    stems = separate_vocals(audio_path)
    vocals_path = str(stems.data.get("vocals_path") or audio_path)
    transcript = transcribe_vocals(vocals_path)
    dossier["analysis_mode"] = "local_dsp_with_optional_voice"
    dossier["premium"] = {
        "stems": _public_stems(stems.to_dict()),
        "transcript": _public_transcript(transcript.to_dict()),
    }
    return dossier


def _public_source(envelope: dict[str, Any]) -> dict[str, Any]:
    data = envelope.get("data", {}) or {}
    metadata = envelope.get("metadata", {}) or {}
    return {
        "status": envelope.get("status"),
        "mode": envelope.get("mode"),
        "source_name": data.get("source_name"),
        "title": data.get("title"),
        "content_hash": metadata.get("content_hash"),
        "cache_hit": metadata.get("cache_hit"),
    }


def _public_dsp(envelope: dict[str, Any]) -> dict[str, Any]:
    data = envelope.get("data", {}) or {}
    metadata = data.get("metadata", {}) or {}
    return {
        "status": envelope.get("status"),
        "mode": envelope.get("mode"),
        "diagnostics": envelope.get("diagnostics", []),
        "data": {
            "metadata": {
                "source_name": metadata.get("source_name"),
                "duration_seconds": metadata.get("duration_seconds"),
                "sample_rate": metadata.get("sample_rate"),
                "section_count": metadata.get("section_count"),
            },
            "acoustic_metrics": data.get("acoustic_metrics", {}),
            "timeline_sections": data.get("timeline_sections", []),
        },
    }


def _public_envelope(envelope: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": envelope.get("status"),
        "mode": envelope.get("mode"),
        "data": envelope.get("data", {}),
        "diagnostics": envelope.get("diagnostics", []),
    }


def _public_stems(envelope: dict[str, Any]) -> dict[str, Any]:
    stems = ((envelope.get("data") or {}).get("stems") or {})
    return {
        "status": envelope.get("status"),
        "mode": envelope.get("mode"),
        "available_stems": list(stems),
        "diagnostics": envelope.get("diagnostics", []),
    }


def _public_transcript(envelope: dict[str, Any]) -> dict[str, Any]:
    data = envelope.get("data", {}) or {}
    return {
        "status": envelope.get("status"),
        "mode": envelope.get("mode"),
        "diagnostics": envelope.get("diagnostics", []),
        "data": {
            "text": str(data.get("text") or "")[:MAX_TRANSCRIPT_CHARS],
            "language": data.get("language"),
            "alignment_status": data.get("alignment_status"),
            "transcription_confidence": data.get("transcription_confidence"),
            "segments": list(data.get("segments", []) or [])[:MAX_TRANSCRIPT_SEGMENTS],
            "word_count": len(data.get("words", []) or []),
        },
    }
