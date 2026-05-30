# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules, copy_metadata


datas = [
    ("app.py", "."),
    ("README.md", "."),
    ("requirements.txt", "."),
    ("core", "core"),
    ("services", "services"),
    ("knowledge_base", "knowledge_base"),
    ("docs", "docs"),
]

binaries = []

for package in (
    "streamlit",
    "altair",
    "pydeck",
    "matplotlib",
    "imageio_ffmpeg",
    "yt_dlp",
    "whisperx",
    "whisper",
    "demucs",
    "torch",
    "torchaudio",
):
    try:
        datas += collect_data_files(package, include_py_files=False)
    except Exception:
        pass
    try:
        binaries += collect_dynamic_libs(package)
    except Exception:
        pass

for dist_name in (
    "streamlit",
    "altair",
    "pydeck",
    "pandas",
    "numpy",
    "scipy",
    "librosa",
    "soundfile",
    "matplotlib",
    "yt-dlp",
    "torch",
    "torchaudio",
    "demucs",
    "whisperx",
    "openai-whisper",
    "anthropic",
    "openai",
    "google-genai",
    "lyricsgenius",
):
    try:
        datas += copy_metadata(dist_name)
    except Exception:
        pass

hiddenimports = [
    "streamlit.web.cli",
    "streamlit.runtime.scriptrunner.magic_funcs",
    "watchdog.observers.winapi",
    "sqlite3",
    "PIL._tkinter_finder",
    "sklearn",
    "sklearn.utils._typedefs",
    "sklearn.neighbors._partition_nodes",
    "librosa",
    "soundfile",
    "numba",
    "llvmlite",
    "torch",
    "torchaudio",
    "demucs",
    "demucs.separate",
    "whisperx",
    "whisper",
    "faster_whisper",
    "ctranslate2",
    "onnxruntime",
    "transformers",
    "anthropic",
    "openai",
    "google.genai",
    "lyricsgenius",
    "yt_dlp",
    "imageio_ffmpeg",
]

for package in (
    "streamlit.runtime",
    "streamlit.web",
):
    try:
        hiddenimports += collect_submodules(package)
    except Exception:
        pass

excludes = [
    "tensorflow",
    "tensorboard",
    "plotly",
    "pytest",
    "IPython",
    "jupyter",
    "notebook",
    "matplotlib.tests",
    "sklearn.tests",
    "scipy.tests",
    "pandas.tests",
    "torch.testing",
    "torch.distributed.elastic",
]


a = Analysis(
    ["desktop_launcher.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AudioAgentDesktop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AudioAgentDesktop",
)
