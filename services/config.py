from __future__ import annotations

import importlib.util
import os
import shutil
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT_DIR / ".cache"
UPLOAD_CACHE_DIR = CACHE_DIR / "uploads"
WEB_CACHE_DIR = CACHE_DIR / "web_ingest"
DSP_CACHE_DIR = CACHE_DIR / "dsp"
LOUDNESS_CACHE_DIR = CACHE_DIR / "loudness"
STEMS_CACHE_DIR = CACHE_DIR / "stems"
TRANSCRIPT_CACHE_DIR = CACHE_DIR / "transcripts"
TMP_DIR = CACHE_DIR / "tmp"
OUTPUT_DIR = ROOT_DIR / "outputs"
KNOWLEDGE_BASE_DIR = ROOT_DIR / "knowledge_base"

AUDIO_EXTENSIONS = ("mp3", "wav", "flac", "ogg", "m4a", "aac")

LLM_PROVIDER_SPECS: dict[str, dict[str, object]] = {
    "anthropic": {
        "label": "Anthropic",
        "env_var": "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-4-20250514",
        "fallback_models": [
            "claude-3-7-sonnet-20250219",
            "claude-3-5-haiku-20241022",
        ],
        "presets": [
            "claude-sonnet-4-20250514",
            "claude-3-7-sonnet-20250219",
            "claude-3-5-haiku-20241022",
        ],
        "sdk_module": "anthropic",
    },
    "openai": {
        "label": "OpenAI",
        "env_var": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
        "fallback_models": [
            "gpt-4o-mini",
            "gpt-5.4-mini",
            "gpt-5.4",
            "gpt-5.5",
            "gpt-5.5-pro",
        ],
        "presets": [
            "gpt-5.5",
            "gpt-5.5-pro",
            "gpt-5.4",
            "gpt-5.4-mini",
            "gpt-4o-mini",
        ],
        "sdk_module": "openai",
    },
    "gemini": {
        "label": "Gemini",
        "env_var": "GEMINI_API_KEY",
        "alt_env_vars": ["GOOGLE_API_KEY"],
        "default_model": "gemini-2.5-flash",
        "fallback_models": [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-3.5-flash",
            "gemini-3.1-flash-lite",
            "gemini-3.1-pro",
        ],
        "presets": [
            "gemini-3.5-flash",
            "gemini-3.1-pro",
            "gemini-3.1-flash-lite",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
        ],
        "sdk_module": "google.genai",
    },
}


def ensure_runtime_dirs() -> None:
    for path in (
        CACHE_DIR,
        UPLOAD_CACHE_DIR,
        WEB_CACHE_DIR,
        DSP_CACHE_DIR,
        LOUDNESS_CACHE_DIR,
        STEMS_CACHE_DIR,
        TRANSCRIPT_CACHE_DIR,
        TMP_DIR,
        OUTPUT_DIR,
        KNOWLEDGE_BASE_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def command_available(command: str) -> bool:
    return shutil.which(command) is not None


def ffmpeg_executable() -> str | None:
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    if importlib.util.find_spec("imageio_ffmpeg") is None:
        return None
    try:
        import imageio_ffmpeg

        candidate = imageio_ffmpeg.get_ffmpeg_exe()
        return candidate if candidate and Path(candidate).exists() else None
    except Exception:
        return None


def ffmpeg_available() -> bool:
    return ffmpeg_executable() is not None


def optional_dependency_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def knowledge_base_path(name: str) -> Path:
    return KNOWLEDGE_BASE_DIR / name


def llm_provider_options() -> list[str]:
    return list(LLM_PROVIDER_SPECS.keys())


def llm_provider_label(provider: str) -> str:
    return str(LLM_PROVIDER_SPECS[provider]["label"])


def llm_default_model(provider: str) -> str:
    return str(LLM_PROVIDER_SPECS[provider]["default_model"])


def llm_model_presets(provider: str) -> list[str]:
    return list(LLM_PROVIDER_SPECS[provider].get("presets", []))


def llm_env_var(provider: str) -> str:
    return str(LLM_PROVIDER_SPECS[provider]["env_var"])


def resolve_llm_api_key(provider: str, explicit_api_key: str | None = None) -> str:
    if explicit_api_key and explicit_api_key.strip():
        return explicit_api_key.strip()

    env_var = llm_env_var(provider)
    candidate = os.getenv(env_var, "").strip()
    if candidate:
        return candidate

    alt_env_vars = LLM_PROVIDER_SPECS[provider].get("alt_env_vars", [])
    for alt_env_var in alt_env_vars:
        candidate = os.getenv(str(alt_env_var), "").strip()
        if candidate:
            return candidate
    return ""


def runtime_capabilities() -> dict[str, bool]:
    return {
        "ffmpeg": ffmpeg_available(),
        "yt_dlp": optional_dependency_available("yt_dlp"),
        "demucs": optional_dependency_available("demucs"),
        "whisperx": optional_dependency_available("whisperx"),
        "openai_whisper": optional_dependency_available("whisper"),
        "lyricsgenius": optional_dependency_available("lyricsgenius"),
        "pyloudnorm": optional_dependency_available("pyloudnorm"),
        "torch": optional_dependency_available("torch"),
        "torchaudio": optional_dependency_available("torchaudio"),
        "anthropic_sdk": optional_dependency_available("anthropic"),
        "openai_sdk": optional_dependency_available("openai"),
        "gemini_sdk": optional_dependency_available("google.genai"),
    }
