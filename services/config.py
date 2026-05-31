from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path


def _resource_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def _default_data_root() -> Path:
    explicit = os.getenv("AUDIOAGENT_DATA_DIR", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    desktop_mode = os.getenv("AUDIOAGENT_DESKTOP_MODE", "").strip().lower() in {"1", "true", "yes"}
    if desktop_mode or getattr(sys, "frozen", False):
        base = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "AudioAgent"
    return ROOT_DIR


ROOT_DIR = _resource_root()
DATA_ROOT_DIR = _default_data_root()
CACHE_DIR = DATA_ROOT_DIR / ".cache"
UPLOAD_CACHE_DIR = CACHE_DIR / "uploads"
WEB_CACHE_DIR = CACHE_DIR / "web_ingest"
DSP_CACHE_DIR = CACHE_DIR / "dsp"
LOUDNESS_CACHE_DIR = CACHE_DIR / "loudness"
STEMS_CACHE_DIR = CACHE_DIR / "stems"
TRANSCRIPT_CACHE_DIR = CACHE_DIR / "transcripts"
TMP_DIR = CACHE_DIR / "tmp"
OUTPUT_DIR = DATA_ROOT_DIR / "outputs"
LOG_DIR = DATA_ROOT_DIR / "logs"
DATABASE_PATH = DATA_ROOT_DIR / "audioagent.db"
KNOWLEDGE_BASE_DIR = ROOT_DIR / "knowledge_base"

AUDIO_EXTENSIONS = ("mp3", "wav", "flac", "ogg", "m4a", "aac")
PREMIUM_RUNTIME_MODULES = {"demucs", "whisperx", "whisper", "torch", "torchaudio"}

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
        LOG_DIR,
        DATABASE_PATH.parent,
        KNOWLEDGE_BASE_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def command_available(command: str) -> bool:
    return shutil.which(command) is not None


def _python_runtime_candidates() -> list[Path]:
    explicit = os.getenv("AUDIOAGENT_PREMIUM_PYTHON", "").strip()
    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser())

    candidates.extend(
        [
            Path(sys.executable).resolve().parent / "runtime" / "premium" / "python.exe",
            ROOT_DIR.parent / "runtime" / "premium" / "python.exe",
            ROOT_DIR / ".runtime" / "premium" / "python.exe",
        ]
    )
    if not getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable))

    system_python = shutil.which("python")
    if system_python:
        candidates.append(Path(system_python))

    unique = []
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if resolved not in unique:
            unique.append(resolved)
    return unique


@lru_cache(maxsize=32)
def _python_module_available(python_executable: str, module_name: str) -> bool:
    try:
        completed = subprocess.run(
            [
                python_executable,
                "-c",
                f"import importlib.util; raise SystemExit(0 if importlib.util.find_spec({module_name!r}) else 1)",
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        return completed.returncode == 0
    except Exception:
        return False


def premium_python_executable(*module_names: str) -> str | None:
    required_modules = tuple(name for name in module_names if name)
    for candidate in _python_runtime_candidates():
        if not candidate.exists() or not candidate.is_file():
            continue
        if getattr(sys, "frozen", False) and candidate == Path(sys.executable).resolve():
            continue
        if required_modules and not all(_python_module_available(str(candidate), name) for name in required_modules):
            continue
        return str(candidate)
    return None


def premium_worker_path() -> Path:
    return ROOT_DIR / "services" / "premium_worker.py"


def premium_subprocess_env(python_executable: str | None = None) -> dict[str, str]:
    env = os.environ.copy()
    if python_executable and "runtime\\premium" in str(Path(python_executable)).lower():
        env["PYTHONNOUSERSITE"] = "1"
    return env


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
    if importlib.util.find_spec(module_name) is not None:
        return True
    if module_name in PREMIUM_RUNTIME_MODULES:
        return premium_python_executable(module_name) is not None
    return False


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
        "premium_runtime": premium_python_executable() is not None,
        "anthropic_sdk": optional_dependency_available("anthropic"),
        "openai_sdk": optional_dependency_available("openai"),
        "gemini_sdk": optional_dependency_available("google.genai"),
    }
