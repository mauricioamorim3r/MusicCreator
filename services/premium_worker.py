from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


def _serialize_transcript(result: dict[str, Any]) -> dict[str, Any]:
    segments = []
    words = []
    for segment in result.get("segments", []):
        segment_text = str(segment.get("text") or "").strip()
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
            word_text = str(word.get("word") or "").strip()
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
    text = str(result.get("text") or "").strip()
    if not text and segments:
        text = "\n".join(segment["text"] for segment in segments).strip()
    return {
        "text": text,
        "language": result.get("language"),
        "segments": segments,
        "words": words,
    }


def _has_text(transcript: dict[str, Any]) -> bool:
    return bool(str(transcript.get("text") or "").strip())


def _transcribe_with_whisperx(audio_path: str) -> dict[str, Any]:
    import whisperx

    device = "cpu"
    audio = whisperx.load_audio(audio_path)
    model = whisperx.load_model("small", device=device, compute_type="int8")
    result = model.transcribe(audio, batch_size=4)
    language_code = result.get("language") or "en"
    transcript = _serialize_transcript(
        {
            "text": result.get("text", ""),
            "language": language_code,
            "segments": result.get("segments", []),
        }
    )
    transcript["alignment_status"] = "not_aligned"
    transcript["transcription_confidence"] = "low" if _has_text(transcript) else "none"
    diagnostics = []
    if not _has_text(transcript):
        diagnostics.append("WhisperX executou, mas não encontrou texto vocal utilizável no áudio.")
        return {"engine": "whisperx", "mode": "empty", "transcript": transcript, "diagnostics": diagnostics}

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
        aligned_transcript = _serialize_transcript(
            {
                "text": transcript["text"],
                "language": language_code,
                "segments": aligned.get("segments", []),
            }
        )
        if _has_text(aligned_transcript):
            transcript = aligned_transcript
        transcript["alignment_status"] = "word_aligned" if transcript.get("words") else "segment_only"
        transcript["transcription_confidence"] = "medium" if transcript.get("words") else "low"
        diagnostics.append(
            "WhisperX executado com alinhamento em nível de palavra."
            if transcript.get("words")
            else "WhisperX gerou texto, mas sem palavras alinhadas. Entregando transcrição bruta por segmento."
        )
    except Exception as exc:
        diagnostics.extend(
            [
                "WhisperX gerou texto, mas o alinhamento falhou. Entregando transcrição bruta.",
                f"Falha no alinhamento: {exc}",
            ]
        )
    return {
        "engine": "whisperx",
        "mode": "premium" if transcript.get("words") else "rough",
        "transcript": transcript,
        "diagnostics": diagnostics,
    }


def _transcribe_with_openai_whisper(audio_path: str) -> dict[str, Any]:
    import whisper

    model = whisper.load_model("base", device="cpu")
    result = model.transcribe(audio_path, fp16=False, verbose=False)
    transcript = _serialize_transcript(result)
    transcript["alignment_status"] = "not_aligned"
    transcript["transcription_confidence"] = "low" if _has_text(transcript) else "none"
    diagnostics = [
        "Transcrição bruta gerada com Whisper sem alinhamento por palavra. Revise antes de usar como letra final."
        if _has_text(transcript)
        else "Whisper executou, mas não encontrou texto vocal utilizável no áudio."
    ]
    return {
        "engine": "openai_whisper",
        "mode": "rough" if _has_text(transcript) else "empty",
        "transcript": transcript,
        "diagnostics": diagnostics,
    }


def transcribe(audio_path: str) -> dict[str, Any]:
    diagnostics = []
    if importlib.util.find_spec("whisperx") is not None:
        try:
            return _transcribe_with_whisperx(audio_path)
        except Exception as exc:
            diagnostics.append(f"WhisperX falhou; fallback Whisper será tentado: {exc}")
    if importlib.util.find_spec("whisper") is not None:
        try:
            payload = _transcribe_with_openai_whisper(audio_path)
            payload["diagnostics"] = diagnostics + payload["diagnostics"]
            return payload
        except Exception as exc:
            diagnostics.append(f"Whisper falhou: {exc}")
    return {
        "engine": "unavailable",
        "mode": "skipped",
        "transcript": {"text": "", "language": None, "segments": [], "words": []},
        "diagnostics": diagnostics or ["WhisperX e Whisper não estão instalados no runtime premium."],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["transcribe"])
    parser.add_argument("--audio", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = transcribe(args.audio)
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
