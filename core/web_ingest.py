"""
web_ingest.py
─────────────
Compatibilidade v2 para download automatizado de áudio via URLs.
Encaminha para o pipeline compartilhado, preservando a API pedida no pacote
de expansão sem duplicar a lógica de cache e ingestão.
"""

from __future__ import annotations

from services.web_ingest import ingest_audio


def download_audio_from_url(url: str, output_dir: str = "temp_audio") -> str:
    """
    Descarrega o áudio de um URL fornecido e converte para WAV.
    Retorna o caminho absoluto do ficheiro descarregado.

    O parâmetro `output_dir` é mantido por compatibilidade com o design
    original do módulo, mas o v2 usa cache determinístico interno.
    """
    del output_dir
    result = ingest_audio(url)
    if result.status != "success":
        detail = result.error or "Falha desconhecida na ingestão por URL."
        raise RuntimeError(detail)
    return result.data["audio_path"]

