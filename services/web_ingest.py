from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from services.config import WEB_CACHE_DIR, ensure_runtime_dirs, ffmpeg_executable, optional_dependency_available
from services.models import IngestResult


def _sha256_path(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _is_valid_url(source: str) -> bool:
    parsed = urlparse(source)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _extract_remote_metadata(source: str) -> dict[str, str]:
    if not optional_dependency_available("yt_dlp"):
        return {}

    try:
        import yt_dlp

        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
            info = ydl.extract_info(source, download=False)
        return {
            "title": str((info or {}).get("title") or "").strip(),
            "artist": str((info or {}).get("artist") or (info or {}).get("uploader") or "").strip(),
            "uploader": str((info or {}).get("uploader") or "").strip(),
        }
    except Exception:
        return {}


def ingest_audio(source: str) -> IngestResult:
    ensure_runtime_dirs()

    if not _is_valid_url(source):
        return IngestResult(
            status="failure",
            error="Informe uma URL http(s) válida para ingestão.",
            diagnostics=["URL rejeitada antes do download."],
            mode="skipped",
        )

    if not optional_dependency_available("yt_dlp"):
        return IngestResult(
            status="failure",
            error="yt-dlp não está instalado no ambiente atual.",
            diagnostics=["Instale yt-dlp para habilitar ingestão por link."],
            mode="skipped",
        )

    ffmpeg_path = ffmpeg_executable()
    if not ffmpeg_path:
        return IngestResult(
            status="failure",
            error="ffmpeg não está disponível no PATH.",
            diagnostics=["yt-dlp depende de ffmpeg para normalizar o áudio em WAV. No Render, use requirements-render.txt com imageio-ffmpeg."],
            mode="skipped",
        )

    source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
    target_dir = WEB_CACHE_DIR / source_hash
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = target_dir / "manifest.json"
    remote_metadata = _extract_remote_metadata(source)

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        cached_path = Path(manifest["audio_path"])
        if cached_path.exists():
            return IngestResult(
                status="success",
                mode="cached",
                data={
                    "audio_path": str(cached_path),
                    "source_url": source,
                    "title": manifest.get("title") or remote_metadata.get("title") or cached_path.stem,
                    "artist": manifest.get("artist") or remote_metadata.get("artist") or "",
                    "source_type": "url",
                },
                diagnostics=["Áudio reaproveitado do cache local."],
                metadata={
                    "cache_hit": True,
                    "audio_sha256": manifest.get("audio_sha256"),
                    "source_hash": source_hash,
                },
            )

    download_template = str(target_dir / "source.%(ext)s")
    command = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--no-playlist",
        "--extract-audio",
        "--audio-format",
        "wav",
        "--audio-quality",
        "0",
        "--ffmpeg-location",
        str(Path(ffmpeg_path).parent),
        "-o",
        download_template,
        source,
    ]

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        diagnostics = [line for line in (exc.stderr or exc.stdout).splitlines() if line][:6]
        return IngestResult(
            status="failure",
            error="Falha ao baixar ou converter o áudio a partir da URL.",
            diagnostics=diagnostics,
            mode="skipped",
        )

    wav_files = sorted(target_dir.glob("*.wav"))
    if not wav_files:
        return IngestResult(
            status="failure",
            error="O download terminou sem produzir um arquivo WAV local.",
            diagnostics=[line for line in completed.stdout.splitlines() if line][-6:],
            mode="skipped",
        )

    downloaded_file = wav_files[0]
    audio_sha256 = _sha256_path(downloaded_file)
    canonical_path = target_dir / f"audio_{audio_sha256[:16]}.wav"
    if downloaded_file != canonical_path:
        downloaded_file.replace(canonical_path)

    manifest = {
        "audio_path": str(canonical_path),
        "audio_sha256": audio_sha256,
        "source_url": source,
        "title": remote_metadata.get("title") or canonical_path.stem,
        "artist": remote_metadata.get("artist") or "",
        "uploader": remote_metadata.get("uploader") or "",
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return IngestResult(
        status="success",
        mode="downloaded",
        data={
            "audio_path": str(canonical_path),
            "source_url": source,
            "title": manifest["title"],
            "artist": manifest["artist"],
            "source_type": "url",
        },
        diagnostics=["Áudio baixado e normalizado em WAV com sucesso."],
        metadata={
            "cache_hit": False,
            "audio_sha256": audio_sha256,
            "source_hash": source_hash,
        },
    )
