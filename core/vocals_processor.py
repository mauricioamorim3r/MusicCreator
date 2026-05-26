"""
vocals_processor.py
───────────────────
Camada de compatibilidade para separação de stems (Demucs) e transcrição
fonética (WhisperX), preservando a API simples do pacote de expansão.
"""

from __future__ import annotations

from services.vocals_processor import separate_vocals, transcribe_vocals


def separate_stems_with_demucs(audio_path: str, output_dir: str = "stems_output") -> dict:
    """
    Executa a separação de stems e devolve um dicionário simples com caminhos.

    O parâmetro `output_dir` é mantido por compatibilidade com a API proposta.
    A implementação v2 usa cache interno e fallback seguro.
    """
    del output_dir
    result = separate_vocals(audio_path)
    stems = result.data.get("stems", {})

    if "vocals" in stems:
        return {
            "vocals": stems.get("vocals"),
            "drums": stems.get("drums"),
            "bass": stems.get("bass"),
            "other": stems.get("other"),
            "instrumental": stems.get("instrumental") or result.data.get("mix_path"),
        }

    vocals_path = result.data.get("vocals_path")
    return {"vocals": vocals_path} if vocals_path else {}


def transcribe_with_whisperx(vocal_audio_path: str) -> str:
    """
    Transcreve a faixa vocal e devolve texto estruturado simples para leitura
    por agentes ou visualização rápida.
    """
    result = transcribe_vocals(vocal_audio_path)
    transcript = result.data

    if transcript.get("segments"):
        lines = []
        for segment in transcript["segments"]:
            start = round(segment.get("start", 0.0), 2)
            end = round(segment.get("end", 0.0), 2)
            text = segment.get("text", "").strip()
            lines.append(f"[{start}s - {end}s] {text}")
        return "\n".join(lines)

    if result.mode == "skipped":
        diagnostic = result.diagnostics[0] if result.diagnostics else "Transcrição ignorada."
        return f"[Aviso: {diagnostic}]"

    if result.error:
        return f"[Erro na transcrição: {result.error}]"

    return transcript.get("text", "") or "[Aviso: Nenhuma transcrição produzida.]"

