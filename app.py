"""
app.py — AudioAgent v2 Foundation
Streamlit shell para ingestão local/web, DSP, premium audio-text e agentes IA.
"""

from __future__ import annotations

from datetime import datetime
import base64
import json
import mimetypes
import os
import re
from pathlib import Path

import matplotlib.pyplot as plt
import streamlit as st
from dotenv import load_dotenv

import core.web_ingest as web_ingest
from services.audio_pipeline import run_audio_pipeline
from services.copilot_attachments import capture_screen, prepare_attachment
from services.config import (
    AUDIO_EXTENSIONS,
    OUTPUT_DIR,
    knowledge_base_path,
    llm_default_model,
    llm_env_var,
    llm_model_presets,
    llm_provider_label,
    llm_provider_options,
    resolve_llm_api_key,
    runtime_capabilities,
)
from services.history_store import load_analysis_history, load_history_run, persist_analysis_run
from services.local_database import clear_copilot_messages, list_copilot_messages, search_analysis_runs
from services.musical_copilot import COPILOT_ACTIONS, ask_copilot
from services.user_settings import load_user_settings, save_user_settings

load_dotenv()
USER_GUIDE_PATH = Path(__file__).resolve().parent / "docs" / "user_guide.md"
SAVED_SETTINGS = load_user_settings()

PLOT_BG = "#09131d"
PLOT_FG = "#f5efe4"
ACCENT = "#ff7a00"
ACCENT2 = "#00d1bf"
ACCENT3 = "#2d6df6"
STAGE_ORDER = ["ingest", "dsp", "loudness", "stems", "transcription", "lyrics_validation", "matcher", "agents"]
STAGE_LABELS = {
    "ingest": "Ingestão",
    "dsp": "DSP",
    "loudness": "Loudness",
    "stems": "Stems",
    "transcription": "Transcrição",
    "lyrics_validation": "Validação da letra",
    "matcher": "Matcher",
    "agents": "Agentes",
}


st.set_page_config(
    page_title="AudioAgent v2 Foundation",
    page_icon="🎵",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
    :root {
        --bg-main: #071018;
        --bg-panel: rgba(10, 19, 28, 0.82);
        --bg-panel-strong: rgba(13, 24, 36, 0.95);
        --line-soft: rgba(120, 160, 190, 0.18);
        --line-strong: rgba(255, 122, 0, 0.35);
        --text-main: #f5efe4;
        --text-soft: #9db0bf;
        --accent-main: #ff7a00;
        --accent-cool: #00d1bf;
        --accent-blue: #2d6df6;
    }
    html, body, [data-testid="stAppViewContainer"] {
        background:
            radial-gradient(circle at top left, rgba(255,122,0,0.16), transparent 26%),
            radial-gradient(circle at top right, rgba(45,109,246,0.14), transparent 28%),
            linear-gradient(180deg, #050b11 0%, #09131d 42%, #071018 100%);
        color: var(--text-main);
    }
    [data-testid="stHeader"], header {
        background: linear-gradient(90deg, rgba(5, 11, 17, 0.96), rgba(9, 19, 29, 0.92)) !important;
        border-bottom: 1px solid rgba(120,160,190,0.12);
    }
    [data-testid="stToolbar"], [data-testid="stDecoration"] {
        color: rgba(245, 239, 228, 0.72) !important;
    }
    body, p, li, label, [data-testid="stMarkdownContainer"] {
        font-family: "IBM Plex Sans", sans-serif;
    }
    h1, h2, h3 {
        font-family: "Bebas Neue", sans-serif;
        letter-spacing: 0.04em;
    }
    .block-container { padding-top: 1.1rem; padding-bottom: 2rem; }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(6, 13, 20, 0.98), rgba(11, 21, 31, 0.98));
        border-right: 1px solid var(--line-soft);
    }
    [data-testid="stSidebar"] * {
        color: #d8e5ef;
    }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"],
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] *,
    [data-testid="stSidebar"] small,
    [data-testid="stSidebar"] p {
        color: #8fa6b8 !important;
    }
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        letter-spacing: 0.06em;
        color: #f5efe4 !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] {
        border-color: rgba(120,160,190,0.18);
        background: rgba(255,255,255,0.025);
        border-radius: 12px;
    }
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] textarea,
    [data-testid="stSidebar"] [data-baseweb="input"] {
        color: #071018 !important;
        background: #f7fbff !important;
        border-radius: 10px;
    }
    [data-testid="stSidebar"] input::placeholder,
    [data-testid="stSidebar"] textarea::placeholder {
        color: #718294 !important;
    }
    [data-testid="stSidebar"] .stButton > button,
    [data-testid="stSidebar"] .stButton > button * {
        color: #120c09 !important;
    }
    [data-testid="stSidebar"] .stButton > button:disabled,
    [data-testid="stSidebar"] .stButton > button:disabled * {
        color: rgba(18, 12, 9, 0.58) !important;
    }
    [data-testid="metric-container"] {
        background: linear-gradient(180deg, rgba(12, 22, 33, 0.96), rgba(8, 16, 25, 0.96));
        border: 1px solid var(--line-soft);
        border-radius: 16px;
        padding: 0.9rem 1rem;
        box-shadow: 0 14px 34px rgba(0, 0, 0, 0.22);
    }
    .stTabs [data-baseweb="tab"] {
        font-size: 0.92rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        border-radius: 999px;
        background: rgba(10, 20, 30, 0.55);
        border: 1px solid rgba(120, 160, 190, 0.12);
        margin-right: 0.35rem;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(90deg, rgba(255,122,0,0.16), rgba(0,209,191,0.12));
        border: 1px solid var(--line-strong);
    }
    .stButton > button, .stDownloadButton > button {
        border-radius: 999px;
        border: 1px solid rgba(255,122,0,0.35);
        background: linear-gradient(90deg, rgba(255,122,0,0.92), rgba(255,140,43,0.92));
        color: #120c09;
        font-weight: 700;
        box-shadow: 0 12px 24px rgba(255, 122, 0, 0.2);
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        border-color: rgba(255,122,0,0.6);
        background: linear-gradient(90deg, rgba(255,143,51,0.98), rgba(255,169,92,0.98));
    }
    .stButton > button:disabled, .stDownloadButton > button:disabled {
        background: linear-gradient(90deg, rgba(255,122,0,0.38), rgba(255,140,43,0.34)) !important;
        border-color: rgba(255,122,0,0.16) !important;
        color: rgba(18, 12, 9, 0.58) !important;
        box-shadow: none !important;
    }
    [data-testid="stFileUploaderDropzone"] {
        background: linear-gradient(180deg, rgba(15, 28, 41, 0.96), rgba(10, 19, 29, 0.96)) !important;
        border: 1px dashed rgba(120,160,190,0.35) !important;
        border-radius: 14px !important;
    }
    [data-testid="stFileUploaderDropzone"] * {
        color: #d8e5ef !important;
    }
    [data-testid="stFileUploaderDropzone"] button {
        background: rgba(255,255,255,0.08) !important;
        border: 1px solid rgba(120,160,190,0.24) !important;
        color: #f5efe4 !important;
        box-shadow: none !important;
    }
    .stTextInput input, .stTextArea textarea {
        background: rgba(245, 249, 252, 0.96) !important;
        color: #071018 !important;
        border: 1px solid rgba(120,160,190,0.2) !important;
        border-radius: 12px !important;
    }
    .stTextInput input::placeholder, .stTextArea textarea::placeholder {
        color: #748699 !important;
    }
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, var(--accent-cool), var(--accent-main)) !important;
    }
    [data-testid="stDataFrame"], [data-testid="stTable"] {
        border-radius: 14px;
        overflow: hidden;
        border: 1px solid rgba(120,160,190,0.14);
    }
    .hero-shell {
        position: relative;
        overflow: hidden;
        border: 1px solid var(--line-soft);
        border-radius: 28px;
        padding: 1.5rem 1.6rem 1.35rem;
        margin-bottom: 1.2rem;
        background:
            radial-gradient(circle at 12% 20%, rgba(255,122,0,0.18), transparent 24%),
            radial-gradient(circle at 88% 16%, rgba(0,209,191,0.14), transparent 26%),
            linear-gradient(135deg, rgba(10, 19, 28, 0.98), rgba(7, 14, 22, 0.98));
        box-shadow: 0 24px 60px rgba(0, 0, 0, 0.34);
    }
    .hero-kicker {
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.24em;
        color: var(--accent-cool);
        margin-bottom: 0.45rem;
        font-weight: 700;
    }
    .hero-title {
        font-family: "Bebas Neue", sans-serif;
        font-size: 3rem;
        line-height: 0.96;
        letter-spacing: 0.04em;
        color: var(--text-main);
        margin: 0;
    }
    .hero-copy {
        max-width: 760px;
        margin-top: 0.5rem;
        color: var(--text-soft);
        font-size: 1rem;
        line-height: 1.6;
    }
    .hero-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.75rem;
        margin-top: 1.15rem;
    }
    .hero-panel {
        border-radius: 18px;
        padding: 0.9rem 1rem;
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(120,160,190,0.14);
        backdrop-filter: blur(10px);
    }
    .hero-label {
        color: var(--text-soft);
        font-size: 0.74rem;
        text-transform: uppercase;
        letter-spacing: 0.14em;
        margin-bottom: 0.35rem;
    }
    .hero-value {
        color: var(--text-main);
        font-size: 1.04rem;
        font-weight: 700;
    }
    .section-intro {
        font-size: 0.9rem;
        color: var(--text-soft);
        margin-top: -0.2rem;
        margin-bottom: 0.85rem;
    }
    .panel-note {
        border-left: 3px solid var(--accent-main);
        padding: 0.8rem 1rem;
        border-radius: 0 14px 14px 0;
        background: rgba(255,255,255,0.025);
        color: var(--text-soft);
        margin-bottom: 0.9rem;
    }
    .studio-grid {
        display: grid;
        grid-template-columns: 1.2fr 0.8fr;
        gap: 1rem;
        margin-bottom: 1rem;
    }
    .studio-card, .matcher-card {
        border-radius: 22px;
        background: linear-gradient(180deg, rgba(12, 22, 33, 0.96), rgba(8, 16, 25, 0.96));
        border: 1px solid var(--line-soft);
        padding: 1rem 1.05rem;
        box-shadow: 0 18px 40px rgba(0, 0, 0, 0.22);
    }
    .studio-card h4, .matcher-card h4 {
        margin: 0 0 0.4rem 0;
        font-family: "Bebas Neue", sans-serif;
        letter-spacing: 0.05em;
        font-size: 1.35rem;
    }
    .studio-card p, .matcher-card p {
        color: var(--text-soft);
        margin: 0.2rem 0 0;
        line-height: 1.55;
    }
    .stat-strip {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.7rem;
        margin-top: 0.8rem;
    }
    .stat-pill {
        border-radius: 16px;
        padding: 0.8rem 0.9rem;
        background: rgba(255,255,255,0.028);
        border: 1px solid rgba(120,160,190,0.14);
    }
    .stat-pill-label {
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.14em;
        color: var(--text-soft);
        margin-bottom: 0.3rem;
    }
    .stat-pill-value {
        font-size: 1rem;
        font-weight: 700;
        color: var(--text-main);
    }
    .matcher-stack {
        display: grid;
        gap: 0.9rem;
        margin-top: 0.9rem;
    }
    .matcher-card {
        position: relative;
        overflow: hidden;
    }
    .matcher-rank {
        position: absolute;
        top: 0.9rem;
        right: 1rem;
        font-family: "Bebas Neue", sans-serif;
        font-size: 1.4rem;
        color: rgba(255,255,255,0.16);
        letter-spacing: 0.08em;
    }
    .matcher-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 0.45rem;
        margin-top: 0.7rem;
    }
    .matcher-chip {
        border-radius: 999px;
        padding: 0.32rem 0.65rem;
        font-size: 0.78rem;
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(120,160,190,0.16);
        color: var(--text-main);
    }
    .matcher-score {
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        padding: 0.34rem 0.72rem;
        border-radius: 999px;
        background: rgba(255,122,0,0.12);
        border: 1px solid rgba(255,122,0,0.24);
        color: #ffd5b2;
        font-weight: 700;
        margin-top: 0.55rem;
    }
    .health-shell {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.8rem;
        border-radius: 18px;
        padding: 0.85rem 1rem;
        margin-bottom: 0.95rem;
        background: linear-gradient(180deg, rgba(12, 22, 33, 0.96), rgba(8, 16, 25, 0.96));
        border: 1px solid rgba(120,160,190,0.14);
    }
    .health-main {
        display: flex;
        align-items: center;
        gap: 0.8rem;
        min-width: 0;
    }
    .health-dot {
        width: 12px;
        height: 12px;
        border-radius: 999px;
        background: var(--accent-cool);
        box-shadow: 0 0 0 rgba(0,209,191,0.5);
        animation: pulseHealth 1.8s infinite;
        flex: 0 0 auto;
    }
    .health-dot.busy {
        background: var(--accent-main);
        box-shadow: 0 0 0 rgba(255,122,0,0.5);
    }
    .health-dot.error {
        background: #ff4b5c;
        box-shadow: 0 0 0 rgba(255,75,92,0.5);
    }
    .health-title {
        color: var(--text-main);
        font-weight: 700;
        margin: 0;
    }
    .health-copy {
        color: var(--text-soft);
        font-size: 0.86rem;
        margin: 0.15rem 0 0;
    }
    .health-side {
        color: var(--text-soft);
        font-size: 0.78rem;
        text-align: right;
        white-space: nowrap;
    }
    @keyframes pulseHealth {
        0% { box-shadow: 0 0 0 0 rgba(0,209,191,0.45); }
        70% { box-shadow: 0 0 0 12px rgba(0,209,191,0); }
        100% { box-shadow: 0 0 0 0 rgba(0,209,191,0); }
    }
    @media (max-width: 980px) {
        .studio-grid { grid-template-columns: 1fr; }
        .stat-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 980px) {
        .hero-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .hero-title { font-size: 2.4rem; }
    }
    @media (max-width: 640px) {
        .hero-grid { grid-template-columns: 1fr; }
        .stat-strip { grid-template-columns: 1fr; }
    }
</style>
""",
    unsafe_allow_html=True,
)


def load_skills() -> dict:
    with knowledge_base_path("skills_templates.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def load_user_guide() -> str:
    if USER_GUIDE_PATH.exists():
        return USER_GUIDE_PATH.read_text(encoding="utf-8")
    return "Guia do usuário não encontrado."


def format_seconds(value: float | int | None) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.2f}s"
    except Exception:
        return "—"


def init_session_defaults() -> None:
    provider_options = llm_provider_options()
    default_provider = str(SAVED_SETTINGS.get("llm_provider", "openai"))
    if default_provider not in provider_options:
        default_provider = provider_options[0]
    saved_models = SAVED_SETTINGS.get("llm_models", {})
    if not isinstance(saved_models, dict):
        saved_models = {}
    default_model = str(
        saved_models.get(default_provider)
        or SAVED_SETTINGS.get("llm_model")
        or llm_default_model(default_provider)
    )

    defaults = {
        "llm_provider_choice": default_provider,
        "llm_provider_last": default_provider,
        "llm_model_preset": default_model,
        "llm_model_input": default_model,
        "persist_api_key_checkbox": bool(SAVED_SETTINGS.get("persist_api_key", False)),
        "auto_llm_fallback_toggle": bool(SAVED_SETTINGS.get("auto_llm_fallback", True)),
        "matcher_source_notes": SAVED_SETTINGS.get("matcher_source_notes", ""),
        "lyric_title_hint": SAVED_SETTINGS.get("lyric_title_hint", ""),
        "lyric_artist_hint": SAVED_SETTINGS.get("lyric_artist_hint", ""),
        "genius_access_token": SAVED_SETTINGS.get("genius_access_token", os.getenv("GENIUS_ACCESS_TOKEN", "")),
        "genius_client_id": SAVED_SETTINGS.get("genius_client_id", os.getenv("GENIUS_CLIENT_ID", "")),
        "genius_client_secret": SAVED_SETTINGS.get("genius_client_secret", os.getenv("GENIUS_CLIENT_SECRET", "")),
        "persist_genius_credentials_checkbox": bool(SAVED_SETTINGS.get("persist_genius_credentials", False)),
        "run_agents_toggle": bool(SAVED_SETTINGS.get("run_agents", True)),
        "enable_premium_toggle": bool(SAVED_SETTINGS.get("enable_premium", False)),
        "n_sections_slider": int(SAVED_SETTINGS.get("n_sections", 8)),
        "runtime_state": "online",
        "runtime_stage": "idle",
        "runtime_message": "Aplicação pronta para uso.",
        "runtime_last_seen": datetime.now().strftime("%H:%M:%S"),
        "copilot_session_id": "audioagent-local-main",
        "copilot_action": "current_analysis",
        "copilot_question": "",
        "copilot_history_query": "",
        "copilot_captured_attachments": [],
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _saved_api_key_for_provider(provider: str) -> str:
    api_keys = SAVED_SETTINGS.get("api_keys", {})
    if not isinstance(api_keys, dict):
        return ""
    return str(api_keys.get(provider, "") or "")


def _saved_model_for_provider(provider: str) -> str:
    models = SAVED_SETTINGS.get("llm_models", {})
    if not isinstance(models, dict):
        return llm_default_model(provider)
    return str(models.get(provider) or SAVED_SETTINGS.get("llm_model") or llm_default_model(provider))


def _configured_fallback_preview(primary_provider: str, primary_model: str, api_key_input: str) -> list[str]:
    preview: list[str] = []
    seen: set[str] = set()
    api_keys = SAVED_SETTINGS.get("api_keys", {})
    models = SAVED_SETTINGS.get("llm_models", {})
    if not isinstance(api_keys, dict):
        api_keys = {}
    if not isinstance(models, dict):
        models = {}

    for provider in llm_provider_options():
        if provider == primary_provider:
            has_key = bool((api_key_input or "").strip()) or bool(resolve_llm_api_key(provider)) or bool(_saved_api_key_for_provider(provider))
            model = primary_model
        else:
            has_key = bool(resolve_llm_api_key(provider)) or bool(str(api_keys.get(provider, "") or "").strip()) or bool(_saved_api_key_for_provider(provider))
            model = str(models.get(provider) or llm_default_model(provider))
        if has_key and provider not in seen:
            preview.append(f"{llm_provider_label(provider)} · {model}")
            seen.add(provider)
    return preview


def persist_user_preferences(
    *,
    llm_provider: str,
    llm_model: str,
    persist_api_key: bool,
    api_key: str,
    auto_llm_fallback: bool,
    run_agents: bool,
    enable_premium: bool,
    n_sections: int,
) -> None:
    api_keys = SAVED_SETTINGS.get("api_keys", {})
    llm_models = SAVED_SETTINGS.get("llm_models", {})
    if not isinstance(api_keys, dict):
        api_keys = {}
    if not isinstance(llm_models, dict):
        llm_models = {}
    api_keys = dict(api_keys)
    llm_models = dict(llm_models)

    if persist_api_key and api_key.strip():
        api_keys[llm_provider] = api_key.strip()
    else:
        api_keys.pop(llm_provider, None)
    llm_models[llm_provider] = llm_model

    updated = {
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "llm_models": llm_models,
        "persist_api_key": persist_api_key,
        "api_keys": api_keys,
        "auto_llm_fallback": auto_llm_fallback,
        "matcher_source_notes": st.session_state.get("matcher_source_notes", ""),
        "lyric_title_hint": st.session_state.get("lyric_title_hint", ""),
        "lyric_artist_hint": st.session_state.get("lyric_artist_hint", ""),
        "persist_genius_credentials": bool(st.session_state.get("persist_genius_credentials_checkbox", False)),
        "genius_access_token": st.session_state.get("genius_access_token", "") if st.session_state.get("persist_genius_credentials_checkbox", False) else "",
        "genius_client_id": st.session_state.get("genius_client_id", "") if st.session_state.get("persist_genius_credentials_checkbox", False) else "",
        "genius_client_secret": st.session_state.get("genius_client_secret", "") if st.session_state.get("persist_genius_credentials_checkbox", False) else "",
        "run_agents": run_agents,
        "enable_premium": enable_premium,
        "n_sections": n_sections,
    }
    save_user_settings(updated)
    SAVED_SETTINGS.clear()
    SAVED_SETTINGS.update(updated)


def render_hero_header() -> None:
    provider = st.session_state.get("llm_provider_choice", "openai")
    model = st.session_state.get("llm_model_input", llm_default_model(provider))
    premium_label = "Premium ativo" if st.session_state.get("enable_premium_toggle") else "Premium desligado"
    agents_label = "Agentes IA ativos" if st.session_state.get("run_agents_toggle") else "Somente análise local"
    sections_label = f"{st.session_state.get('n_sections_slider', 8)} blocos estruturais"
    matcher_label = "Matcher com contexto" if st.session_state.get("matcher_source_notes", "").strip() else "Matcher catálogo local"
    st.markdown(
        f"""
        <section class="hero-shell">
            <div class="hero-kicker">Music intelligence workstation</div>
            <h1 class="hero-title">AudioAgent</h1>
            <div class="hero-copy">
                Uma bancada de análise musical para transformar áudio em leitura estrutural, letra validada,
                candidatos de mashup e direção criativa pronta para produção.
            </div>
            <div class="hero-grid">
                <div class="hero-panel">
                    <div class="hero-label">LLM atual</div>
                    <div class="hero-value">{llm_provider_label(provider)} · {model}</div>
                </div>
                <div class="hero-panel">
                    <div class="hero-label">Modo criativo</div>
                    <div class="hero-value">{agents_label}</div>
                </div>
                <div class="hero-panel">
                    <div class="hero-label">Motor vocal</div>
                    <div class="hero-value">{premium_label}</div>
                </div>
                <div class="hero-panel">
                    <div class="hero-label">Leitura estrutural</div>
                    <div class="hero-value">{sections_label} · {matcher_label}</div>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    render_runtime_health_banner()


def _active_llm_options(
    *,
    llm_provider: str,
    llm_model: str,
    api_key_input: str,
    auto_llm_fallback: bool,
) -> dict:
    return {
        "provider": llm_provider,
        "model": llm_model,
        "api_key": api_key_input,
        "fallback_enabled": auto_llm_fallback,
        "configured_api_keys": SAVED_SETTINGS.get("api_keys", {}),
        "configured_models": SAVED_SETTINGS.get("llm_models", {}),
    }


def render_copilot_panel(
    *,
    llm_provider: str,
    llm_model: str,
    api_key_input: str,
    auto_llm_fallback: bool,
) -> None:
    session_id = str(st.session_state.get("copilot_session_id", "audioagent-local-main"))
    with st.expander("🎛️ Copiloto Musical · pergunte, consulte e compare", expanded=False):
        st.caption(
            "O copiloto usa a LLM configurada e acessa somente dados autorizados desta instalação. "
            "Ele não executa comandos do sistema e não faz pesquisa web sem uma integração verificável."
        )
        action = st.selectbox(
            "O que você quer que o copiloto faça?",
            options=list(COPILOT_ACTIONS),
            key="copilot_action",
            format_func=lambda value: COPILOT_ACTIONS[value],
        )

        history_query = ""
        selected_run_ids: list[str] = []
        if action in {"history_search", "compare_runs"}:
            history_query = st.text_input(
                "Filtrar histórico por música, artista, link ou ID",
                key="copilot_history_query",
                placeholder="Ex.: Armin, Madonna, YouTube...",
            )
            history_entries = search_analysis_runs(history_query, limit=12)
            if history_entries:
                labels = {
                    str(entry["run_id"]): (
                        f"{entry.get('source_title') or 'Sem título'} · "
                        f"{entry.get('source_artist') or 'artista não identificado'} · "
                        f"{str(entry.get('timestamp', ''))[:19]}"
                    )
                    for entry in history_entries
                }
                if action == "compare_runs":
                    selected_run_ids = st.multiselect(
                        "Escolha até 3 análises para comparar",
                        options=list(labels),
                        format_func=lambda run_id: labels[run_id],
                        max_selections=3,
                        key="copilot_selected_runs",
                    )
                else:
                    selected_run_ids = [str(entry["run_id"]) for entry in history_entries[:5]]
                    st.caption(f"{len(history_entries)} rodada(s) local(is) encontrada(s).")
            else:
                st.info("Nenhuma análise local corresponde ao filtro informado.")

        st.markdown("#### Anexos opcionais")
        st.caption(
            "Você pode anexar telas, PDFs, documentos e planilhas. "
            "A captura de tela só acontece quando você clicar no botão abaixo."
        )
        uploaded_attachments = st.file_uploader(
            "Anexar arquivos para o Copiloto",
            type=["png", "jpg", "jpeg", "webp", "gif", "txt", "md", "json", "csv", "log", "yaml", "yml", "pdf", "docx", "xlsx"],
            accept_multiple_files=True,
            key="copilot_attachment_uploads",
            help="Limite de 15 MB por arquivo. No máximo quatro anexos são enviados em uma pergunta.",
        )
        col_capture, col_remove = st.columns(2)
        capture_clicked = col_capture.button("📷 Capturar tela agora", use_container_width=True)
        remove_clicked = col_remove.button("Remover capturas", use_container_width=True)

        if capture_clicked:
            try:
                captured = list(st.session_state.get("copilot_captured_attachments", []))
                captured.append(capture_screen())
                st.session_state["copilot_captured_attachments"] = captured[-2:]
                st.success("Tela capturada localmente. Revise o preview antes de perguntar.")
            except Exception as exc:
                st.error(f"Falha ao capturar tela: {exc}")
        if remove_clicked:
            st.session_state["copilot_captured_attachments"] = []
            st.rerun()

        attachments: list[dict] = []
        for uploaded_attachment in (uploaded_attachments or [])[:4]:
            try:
                attachments.append(
                    prepare_attachment(uploaded_attachment.name, uploaded_attachment.getvalue())
                )
            except Exception as exc:
                st.warning(f"`{uploaded_attachment.name}` não pôde ser anexado: {exc}")
        attachments.extend(st.session_state.get("copilot_captured_attachments", []))
        attachments = attachments[:4]

        if attachments:
            st.caption(
                "Anexos prontos: "
                + ", ".join(
                    f"{attachment.get('name')} ({attachment.get('kind')})"
                    for attachment in attachments
                )
            )
            captured_images = [
                attachment for attachment in st.session_state.get("copilot_captured_attachments", [])
                if attachment.get("image_base64")
            ]
            if captured_images:
                with st.expander("Revisar última captura de tela", expanded=False):
                    st.image(
                        base64.b64decode(captured_images[-1]["image_base64"]),
                        caption="Captura local que será enviada junto com a pergunta.",
                        use_container_width=True,
                    )

        question = st.text_area(
            "Pergunta para o Copiloto",
            key="copilot_question",
            placeholder=(
                "Ex.: explique a estrutura desta faixa em linguagem simples; "
                "compare as duas análises; quais gargalos aparecem no histórico?"
            ),
            height=96,
        )
        col_ask, col_clear = st.columns([0.72, 0.28])
        ask_clicked = col_ask.button("Perguntar ao Copiloto", type="primary", use_container_width=True)
        clear_clicked = col_clear.button("Limpar conversa", use_container_width=True)

        if clear_clicked:
            clear_copilot_messages(session_id)
            st.rerun()

        if ask_clicked:
            if action == "compare_runs" and len(selected_run_ids) < 2:
                st.warning("Escolha pelo menos duas análises salvas para executar uma comparação.")
            else:
                try:
                    with st.spinner("Copiloto organizando os dados locais e consultando a LLM..."):
                        response = ask_copilot(
                            session_id=session_id,
                            question=question,
                            action=action,
                            pipeline_state=st.session_state.get("pipeline"),
                            llm_options=_active_llm_options(
                                llm_provider=llm_provider,
                                llm_model=llm_model,
                                api_key_input=api_key_input,
                                auto_llm_fallback=auto_llm_fallback,
                            ),
                            history_query=history_query,
                            selected_run_ids=selected_run_ids,
                            attachments=attachments,
                        )
                    if response.get("fallback_used"):
                        st.info(
                            f"Fallback de LLM utilizado: {response.get('label')} · {response.get('model')}."
                        )
                except Exception as exc:
                    st.error(f"Copiloto indisponível: {exc}")

        messages = list_copilot_messages(session_id, limit=10)
        if messages:
            st.markdown("#### Conversa local")
            for message in messages:
                role = "assistant" if message.get("role") == "assistant" else "user"
                with st.chat_message(role):
                    st.markdown(str(message.get("content", "")))
                    if role == "assistant" and message.get("provider"):
                        st.caption(f"{message.get('provider')} · {message.get('model')}")
        else:
            st.caption(
                "Ainda não há mensagens. Você pode começar perguntando o que significa o BPM, "
                "pedindo um resumo da análise aberta ou consultando análises antigas."
            )


def build_performance_notes(performance: dict, analysis_context: dict, agents_result: dict) -> list[str]:
    notes: list[str] = []
    total_elapsed = float((performance or {}).get("total_elapsed_seconds") or 0.0)
    slowest_stage = str((performance or {}).get("slowest_stage") or "")
    stage_timings = (performance or {}).get("stage_timings", []) or []
    stage_map = {item.get("stage"): item for item in stage_timings}
    ingest_seconds = float(((stage_map.get("ingest") or {}).get("elapsed_seconds")) or 0.0)
    premium_seconds = float(((stage_map.get("stems") or {}).get("elapsed_seconds")) or 0.0) + float(
        ((stage_map.get("transcription") or {}).get("elapsed_seconds")) or 0.0
    )
    agent_seconds = float(((stage_map.get("agents") or {}).get("elapsed_seconds")) or 0.0)
    retry_count = int((((agents_result or {}).get("metadata") or {}).get("attempt_count")) or 0)

    if total_elapsed >= 60:
        notes.append(f"Esta rodada levou {format_seconds(total_elapsed)} no total, então ela já entra na faixa de análise pesada.")
    if ingest_seconds >= 10:
        notes.append("A ingestão demorou bastante. Isso costuma acontecer quando o link precisa baixar, transcodificar e normalizar o áudio antes do DSP.")
    if analysis_context.get("enable_premium") and premium_seconds >= 20:
        notes.append("A parte premium foi um dos gargalos. Demucs e WhisperX costumam pesar bastante quando estão rodando em CPU.")
    if agent_seconds >= 12:
        notes.append("A etapa de agentes ficou lenta. Isso normalmente vem de múltiplas chamadas ao provedor, latência de rede e re-prompting.")
    if retry_count > 1:
        notes.append(f"A auditoria acionou {retry_count} tentativas na matriz de agentes, o que aumenta o tempo final.")
    if slowest_stage and not notes:
        notes.append(f"O estágio mais lento desta rodada foi `{STAGE_LABELS.get(slowest_stage, slowest_stage)}`.")
    return notes


def render_stage_table(stage_log: list[dict], performance: dict | None = None, analysis_context: dict | None = None, agents_result: dict | None = None) -> None:
    if not stage_log:
        st.info("Os estágios do pipeline aparecerão aqui após a análise.")
        return
    performance = performance or {}
    analysis_context = analysis_context or {}
    agents_result = agents_result or {}

    if performance:
        col_total, col_slowest, col_runtime = st.columns(3)
        col_total.metric("Tempo total", format_seconds(performance.get("total_elapsed_seconds")))
        col_slowest.metric("Gargalo principal", STAGE_LABELS.get(performance.get("slowest_stage", ""), "—"))
        col_runtime.metric("Tempo do gargalo", format_seconds(performance.get("slowest_stage_seconds")))

        notes = build_performance_notes(performance, analysis_context, agents_result)
        for note in notes:
            st.caption(note)

        timing_rows = []
        for item in performance.get("stage_timings", []):
            timing_rows.append(
                {
                    "Etapa": STAGE_LABELS.get(item.get("stage", ""), item.get("stage", "")),
                    "Status final": item.get("status", ""),
                    "Tempo": format_seconds(item.get("elapsed_seconds")),
                    "Resumo": item.get("message", ""),
                }
            )
        if timing_rows:
            st.markdown("#### Tempos por etapa")
            st.dataframe(timing_rows, use_container_width=True, hide_index=True)

    st.markdown("#### Log detalhado")
    st.dataframe(stage_log, use_container_width=True, hide_index=True)


def extract_style_block(prompt_text: str) -> tuple[str, int]:
    if "---STYLE PROMPT---" in prompt_text and "---FIM DO STYLE PROMPT---" in prompt_text:
        start = prompt_text.index("---STYLE PROMPT---") + len("---STYLE PROMPT---")
        end = prompt_text.index("---FIM DO STYLE PROMPT---")
        style_block = prompt_text[start:end].strip()
    else:
        style_block = prompt_text.strip()
    return style_block, len(style_block)


def extract_audit_score(audit_text: str) -> int | None:
    match = re.search(r"(\d+)\s*/\s*100", audit_text or "")
    return int(match.group(1)) if match else None


def shorten_text(text: str, limit: int = 220) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def format_history_label(entry: dict) -> str:
    title = entry.get("source_title") or "analysis"
    timestamp = str(entry.get("timestamp", "")).replace("T", " ")[:19]
    status = entry.get("status", "unknown")
    return f"{timestamp} · {title} · {status}"


def mark_runtime_status(state: str, stage: str, message: str) -> None:
    st.session_state["runtime_state"] = state
    st.session_state["runtime_stage"] = stage
    st.session_state["runtime_message"] = message
    st.session_state["runtime_last_seen"] = datetime.now().strftime("%H:%M:%S")


def render_runtime_health_banner() -> None:
    state = st.session_state.get("runtime_state", "online")
    stage = st.session_state.get("runtime_stage", "idle")
    message = st.session_state.get("runtime_message", "Aplicação pronta para uso.")
    last_seen = st.session_state.get("runtime_last_seen", "--:--:--")
    title_map = {
        "online": "Aplicação online",
        "running": "Processamento em andamento",
        "error": "Atenção necessária",
    }
    title = title_map.get(state, "Aplicação online")
    dot_class = "busy" if state == "running" else "error" if state == "error" else ""
    st.markdown(
        f"""
        <section class="health-shell">
            <div class="health-main">
                <div class="health-dot {dot_class}"></div>
                <div>
                    <p class="health-title">{title}</p>
                    <p class="health-copy">{message}</p>
                </div>
            </div>
            <div class="health-side">
                Etapa: {stage}<br/>
                Último sinal: {last_seen}
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def run_analysis_flow(
    *,
    uploaded_file,
    source_url: str,
    run_agents: bool,
    enable_premium: bool,
    n_sections: int,
    llm_provider: str,
    llm_model: str,
    api_key_input: str,
    auto_llm_fallback: bool,
    status_placeholder,
    progress_bar,
) -> None:
    stage_updates: dict[str, dict] = {}
    mark_runtime_status("running", "preparing", "Preparando a análise e organizando o pipeline.")

    def update_progress(stage_updates: dict[str, dict]) -> None:
        rows = []
        for index, stage in enumerate(STAGE_ORDER):
            info = stage_updates.get(stage)
            if not info:
                rows.append({"Etapa": STAGE_LABELS[stage], "Status": "pendente", "Mensagem": "Aguardando"})
                continue
            rows.append({"Etapa": STAGE_LABELS[stage], "Status": info["status"], "Mensagem": info["message"]})
            progress_bar.progress(min((index + 1) / len(STAGE_ORDER), 1.0), text=f"{STAGE_LABELS[stage]}: {info['message']}")
        status_placeholder.dataframe(rows, use_container_width=True, hide_index=True)

    update_progress(stage_updates)

    def progress_callback(stage: str, status: str, message: str) -> None:
        stage_updates[stage] = {"status": status, "message": message}
        runtime_state = "error" if status == "failure" else "running"
        mark_runtime_status(runtime_state, STAGE_LABELS.get(stage, stage), message)
        update_progress(stage_updates)

    source_fingerprint = uploaded_file.name if uploaded_file is not None else source_url.strip()
    if st.session_state.get("source_fingerprint") != source_fingerprint:
        st.session_state.pop("pipeline", None)
        st.session_state["source_fingerprint"] = source_fingerprint

    skills = None
    if run_agents:
        try:
            skills = load_skills()
        except Exception as exc:
            st.error(f"Falha ao carregar a base de skills: {exc}")
            st.stop()

    upload_name = uploaded_file.name if uploaded_file is not None else None
    upload_bytes = uploaded_file.getvalue() if uploaded_file is not None else None
    pipeline_result = run_audio_pipeline(
        upload_name=upload_name,
        upload_bytes=upload_bytes,
        source_url=None if uploaded_file is not None else source_url.strip() or None,
        n_sections=n_sections,
        run_agents=run_agents,
        enable_premium=enable_premium,
        skills=skills,
        agent_options={
            "provider": llm_provider,
            "model": llm_model,
            "api_key": api_key_input,
            "fallback_enabled": auto_llm_fallback,
            "configured_api_keys": SAVED_SETTINGS.get("api_keys", {}),
            "configured_models": SAVED_SETTINGS.get("llm_models", {}),
        },
        matcher_sources=st.session_state.get("matcher_source_notes", ""),
        lyric_verification_options={
            "title_hint": st.session_state.get("lyric_title_hint", ""),
            "artist_hint": st.session_state.get("lyric_artist_hint", ""),
            "genius_token": st.session_state.get("genius_access_token", ""),
            "genius_client_id": st.session_state.get("genius_client_id", ""),
            "genius_client_secret": st.session_state.get("genius_client_secret", ""),
        },
        progress_callback=progress_callback,
    )

    st.session_state["pipeline"] = pipeline_result.to_dict()
    history_entry = persist_analysis_run(st.session_state["pipeline"])
    st.session_state["last_history_entry"] = history_entry
    if pipeline_result.status == "success":
        agent_outputs = ((pipeline_result.data.get("agents") or {}).get("data") or {}).copy()
        agents_metadata = ((pipeline_result.data.get("agents") or {}).get("metadata") or {})
        warnings = (pipeline_result.data.get("warnings") or []) if pipeline_result.data else []
        if pipeline_result.data.get("matcher"):
            agent_outputs.setdefault("mashup_matcher", "")
        st.session_state["agent_outputs"] = agent_outputs
        mark_runtime_status("online", "idle", "Aplicação online. Última análise concluída com sucesso.")
        progress_bar.progress(1.0, text="Pipeline concluído.")
        if pipeline_result.mode == "completed_with_warnings":
            st.warning("⚠️ Análise concluída com ressalvas, mas o trabalho já feito foi preservado.")
            for item in warnings:
                st.caption(str(item))
        else:
            st.success("✅ Análise concluída.")
        if agents_metadata.get("llm_fallback_used"):
            st.info(
                "Fallback automático de LLM acionado com sucesso. "
                f"Rodada concluída em {llm_provider_label(agents_metadata.get('llm_provider', llm_provider))} "
                f"· {agents_metadata.get('llm_model', llm_model)}."
            )
        st.caption(f"Histórico salvo: `{history_entry.get('run_id', '')}`")
    else:
        mark_runtime_status("error", "idle", pipeline_result.error or "A execução falhou. Revise o histórico técnico.")
        st.error(pipeline_result.error or "O pipeline falhou.")
        if pipeline_result.diagnostics:
            with st.expander("Detalhes técnicos da falha", expanded=False):
                for item in pipeline_result.diagnostics:
                    st.code(str(item), language=None)
        st.caption(f"Falha registrada no histórico: `{history_entry.get('run_id', '')}`")


def render_audio_preview(pipeline: dict, uploaded_file) -> None:
    source = pipeline.get("source", {})
    source_data = source.get("data", {})
    audio_path = source_data.get("audio_path")
    if uploaded_file is not None:
        st.audio(uploaded_file)
    elif audio_path and Path(audio_path).exists():
        st.audio(audio_path)


def render_dsp_tab(payload: dict, loudness_result: dict | None = None) -> None:
    metrics = payload["acoustic_metrics"]
    meta = payload["metadata"]
    duration = meta["duration_seconds"]
    loudness_result = loudness_result or {}
    loudness_data = loudness_result.get("data", {}) or {}

    st.subheader("📊 Métricas Acústicas")
    st.markdown(
        '<div class="section-intro">Leitura matemática do áudio: andamento, tonalidade, energia por faixa e comportamento estrutural.</div>',
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("BPM", f"{metrics['bpm_measured']:.1f}")
    c2.metric("Tom", f"{metrics['key_note']} {metrics['key_mode'].capitalize()}")
    c3.metric("Camelot", metrics["camelot_key"])
    c4.metric("Duração", f"{int(duration // 60)}:{int(duration % 60):02d}")
    c5.metric("Sample Rate", f"{meta['sample_rate'] // 1000} kHz")

    if loudness_data:
        st.subheader("Loudness e Dinâmica")
        l1, l2, l3, l4, l5 = st.columns(5)
        l1.metric("LUFS integrado", f"{loudness_data.get('integrated_lufs', 'n/d')}")
        l2.metric("RMS dBFS", f"{loudness_data.get('rms_loudness_dbfs', 'n/d')}")
        l3.metric("Sample Peak", f"{loudness_data.get('sample_peak_dbfs', 'n/d')} dBFS")
        l4.metric("Range proxy", f"{loudness_data.get('loudness_range_proxy_lu', 'n/d')} LU")
        l5.metric("Crest Factor", f"{loudness_data.get('crest_factor_db', 'n/d')} dB")
        diagnostics = loudness_result.get("diagnostics", [])
        if diagnostics:
            st.caption(" | ".join(diagnostics))

    col_chart, col_table = st.columns([3, 2])
    with col_chart:
        st.subheader("Balanço Espectral")
        freq_dist = metrics["frequency_distribution"]
        bands = ["Graves\n20–250 Hz", "Médios\n250–4k Hz", "Agudos\n4k–20k Hz"]
        values = [freq_dist["low_energy_db"], freq_dist["mid_energy_db"], freq_dist["high_energy_db"]]
        colors = [ACCENT, ACCENT2, ACCENT3]

        fig, ax = plt.subplots(figsize=(6, 3), facecolor=PLOT_BG)
        ax.set_facecolor(PLOT_BG)
        bars = ax.bar(bands, values, color=colors, width=0.5, edgecolor="#2d2d3d")
        for bar, value in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.5,
                f"{value:.1f} dB",
                ha="center",
                va="bottom",
                color=PLOT_FG,
                fontsize=9,
            )
        ax.set_ylabel("Energia (dB)", color=PLOT_FG, fontsize=9)
        ax.tick_params(colors=PLOT_FG, labelsize=8)
        for spine in ax.spines.values():
            spine.set_edgecolor("#2d2d3d")
        ax.yaxis.grid(True, color="#2d2d3d", linestyle="--", linewidth=0.5)
        ax.set_axisbelow(True)
        plt.tight_layout()
        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

    with col_table:
        st.subheader("Métricas Avançadas")
        st.dataframe(
            {
                "Métrica": ["Largura Espectral", "Zero Crossing Rate", "Flatness Espectral"],
                "Valor": [
                    f"{metrics.get('spectral_bandwidth_hz', 0):.0f} Hz",
                    f"{metrics.get('zero_crossing_rate', 0):.4f}",
                    f"{metrics.get('spectral_flatness', 0):.5f}",
                ],
            },
            use_container_width=True,
            hide_index=True,
        )

    if "_energy_curve" in payload:
        st.subheader("Curva de Energia (RMS)")
        energy_curve = payload["_energy_curve"]
        fig2, ax2 = plt.subplots(figsize=(10, 2.5), facecolor=PLOT_BG)
        ax2.set_facecolor(PLOT_BG)
        ax2.plot(energy_curve["times"], energy_curve["rms_values"], color=ACCENT, linewidth=0.9, alpha=0.9)
        ax2.fill_between(energy_curve["times"], energy_curve["rms_values"], alpha=0.25, color=ACCENT)
        ax2.set_xlabel("Tempo (s)", color=PLOT_FG, fontsize=8)
        ax2.set_ylabel("RMS", color=PLOT_FG, fontsize=8)
        ax2.tick_params(colors=PLOT_FG, labelsize=7)
        for spine in ax2.spines.values():
            spine.set_edgecolor("#2d2d3d")
        ax2.yaxis.grid(True, color="#2d2d3d", linestyle="--", linewidth=0.4)
        ax2.set_axisbelow(True)
        plt.tight_layout()
        st.pyplot(fig2, use_container_width=True)
        plt.close(fig2)

    st.subheader("Seções Detectadas")
    sections_display = []
    for section in payload["timeline_sections"]:
        energy_pct = section["relative_energy_score"]
        bar = "█" * int(energy_pct * 10) + "░" * (10 - int(energy_pct * 10))
        sections_display.append(
            {
                "Seção": section.get("section_label", "—"),
                "Início": section["timestamp_start"],
                "Fim": section["timestamp_end"],
                "Energia": f"{energy_pct:.0%}  {bar}",
                "Stem Dominante": section["dominant_stem"].capitalize(),
            }
        )
    st.dataframe(sections_display, use_container_width=True, hide_index=True)

    with st.expander("📋 Payload JSON Completo (sem curva de energia)"):
        clean_display = {k: v for k, v in payload.items() if not k.startswith("_")}
        st.json(clean_display)


def render_markdown_result(title: str, body: str, empty_message: str) -> None:
    st.subheader(title)
    if body:
        st.markdown(body)
        with st.expander("📋 Copiar texto bruto"):
            st.code(body, language=None)
    else:
        st.info(empty_message)


def render_prompt_tab(prompt_text: str) -> None:
    st.subheader("🎯 Suno AI — Style Prompt")
    st.markdown(
        '<div class="section-intro">Prompt criativo estruturado para uso em Custom Mode, com estilo, letra e exclusões separadas.</div>',
        unsafe_allow_html=True,
    )
    if not prompt_text:
        st.info("Ative os agentes e rode a análise para gerar o prompt do Suno.")
        return

    style_block, char_count = extract_style_block(prompt_text)
    _, col_metric = st.columns([3, 1])
    with col_metric:
        st.metric(
            "Caracteres",
            f"{char_count}/1000",
            delta="OK" if char_count <= 1000 else "EXCEDE LIMITE",
            delta_color="normal" if char_count <= 1000 else "inverse",
        )
    st.markdown(prompt_text)
    st.divider()
    st.subheader("📋 Style Prompt — Pronto para Copiar")
    st.code(style_block, language=None)


def render_audit_tab(audit_text: str, retry_metadata: dict) -> None:
    st.subheader("⚖️ Auditoria de Originalidade")
    st.markdown(
        '<div class="section-intro">Checagem preventiva de similaridade para reduzir risco criativo antes de transformar a análise em produção.</div>',
        unsafe_allow_html=True,
    )
    if not audit_text:
        st.info("Ative os agentes e rode a análise para gerar a auditoria.")
        return

    score_val = None
    match = re.search(r"(\d+)/100", audit_text)
    if match:
        score_val = int(match.group(1))

    if score_val is not None:
        col_score, col_bar = st.columns([1, 3])
        with col_score:
            delta_color = "normal" if score_val >= 85 else "off" if score_val >= 70 else "inverse"
            st.metric("Score", f"{score_val}/100", delta_color=delta_color)
        with col_bar:
            fig3, ax3 = plt.subplots(figsize=(6, 0.6), facecolor=PLOT_BG)
            ax3.set_facecolor(PLOT_BG)
            bar_color = ACCENT2 if score_val >= 85 else ACCENT3 if score_val >= 70 else ACCENT
            ax3.barh([""], [100], color="#2d2d3d", height=0.5, alpha=0.4)
            ax3.barh([""], [score_val], color=bar_color, height=0.5)
            ax3.set_xlim(0, 100)
            ax3.axis("off")
            plt.tight_layout(pad=0)
            st.pyplot(fig3, use_container_width=True)
            plt.close(fig3)

    if retry_metadata:
        st.caption(
            f"Tentativas: {retry_metadata.get('attempt_count', 1)} | "
            f"Melhor rodada: {retry_metadata.get('best_attempt', 1)} | "
            f"Limiar de re-prompt: {retry_metadata.get('retry_threshold', 70)}"
        )
        if retry_metadata.get("retry_history"):
            history_rows = [
                {"Tentativa": item["attempt"], "Score": item.get("score")}
                for item in retry_metadata["retry_history"]
            ]
            st.dataframe(history_rows, use_container_width=True, hide_index=True)

    st.markdown(audit_text)
    with st.expander("📋 Copiar texto bruto"):
        st.code(audit_text, language=None)


def render_transcript_tab(transcript_result: dict) -> None:
    st.subheader("🎤 Letra & Prosódia")
    st.markdown(
        '<div class="section-intro">Quando a análise premium consegue captar voz, este painel mostra o melhor rascunho disponível: alinhado por palavra quando possível, ou bruto por segmento quando o alinhamento falha.</div>',
        unsafe_allow_html=True,
    )
    mode = transcript_result.get("mode")
    diagnostics = transcript_result.get("diagnostics", [])
    transcript = transcript_result.get("data", {})
    alignment_status = transcript.get("alignment_status")
    confidence = transcript.get("transcription_confidence")

    if mode:
        st.caption(
            f"Modo: `{mode}`"
            + (f" | Alinhamento: `{alignment_status}`" if alignment_status else "")
            + (f" | Confiança: `{confidence}`" if confidence else "")
        )

    if transcript.get("text"):
        if mode == "rough":
            st.warning(
                "Transcrição bruta: o app capturou texto vocal, mas não conseguiu alinhar tudo com precisão. "
                "Use como rascunho de estudo, não como letra oficial."
            )
        st.markdown("### Texto vocal capturado")
        st.write(transcript["text"])
        if transcript.get("words"):
            st.markdown("### Timeline alinhada por palavra")
            rows = [
                {
                    "Word": item["word"],
                    "Start": round(item["start"], 2),
                    "End": round(item["end"], 2),
                    "Score": round(item.get("score", 0.0), 2),
                }
                for item in transcript.get("words", [])[:200]
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)
        elif transcript.get("segments"):
            st.markdown("### Timeline bruta por segmento")
            st.dataframe(
                [
                    {
                        "Início": round(item.get("start", 0.0), 2),
                        "Fim": round(item.get("end", 0.0), 2),
                        "Texto": item.get("text", ""),
                    }
                    for item in transcript.get("segments", [])[:80]
                ],
                use_container_width=True,
                hide_index=True,
            )
    else:
        if mode == "skipped":
            st.info("A transcrição premium não foi executada nesta rodada.")
        elif mode == "fallback":
            st.info("O pipeline usou um fallback e não gerou transcrição alinhada.")
        elif mode == "empty":
            st.info("O motor de transcrição rodou, mas não captou texto vocal utilizável nesta música.")
        else:
            st.info("Nenhuma letra alinhada foi produzida para esta análise.")

    if diagnostics:
        st.caption(" | ".join(diagnostics))


def build_transcript_export(transcript_result: dict, lyric_validation_result: dict) -> str:
    transcript = transcript_result.get("data", {}) or {}
    lines = ["AudioAgent - Letra & Prosódia", "=" * 60, ""]
    lines.append(f"Modo de transcrição: {transcript_result.get('mode', '')}")
    if transcript.get("alignment_status"):
        lines.append(f"Alinhamento: {transcript.get('alignment_status')}")
    if transcript.get("transcription_confidence"):
        lines.append(f"Confiança: {transcript.get('transcription_confidence')}")
    if transcript_result.get("diagnostics"):
        lines.append("Diagnósticos: " + " | ".join(transcript_result["diagnostics"]))
    if lyric_validation_result:
        lines.append(f"Validação online: {lyric_validation_result.get('mode', '')}")
        if lyric_validation_result.get("diagnostics"):
            lines.append("Validação: " + " | ".join(lyric_validation_result["diagnostics"]))
    lines.append("")
    if transcript.get("text"):
        lines.append("Letra transcrita")
        lines.append("-" * 60)
        lines.append(transcript["text"])
        lines.append("")
    if transcript.get("words"):
        lines.append("Timeline por palavra")
        lines.append("-" * 60)
        for item in transcript["words"]:
            lines.append(
                f"[{round(item['start'], 2):>6}s - {round(item['end'], 2):>6}s] "
                f"{item['word']} (score={round(item.get('score', 0.0), 2)})"
            )
    elif transcript.get("segments"):
        lines.append("Timeline bruta por segmento")
        lines.append("-" * 60)
        for item in transcript["segments"]:
            lines.append(
                f"[{round(item.get('start', 0.0), 2):>6}s - {round(item.get('end', 0.0), 2):>6}s] "
                f"{item.get('text', '').strip()}"
            )
    return "\n".join(lines).strip() + "\n"


init_session_defaults()


def _file_size_label(path: Path) -> str:
    if not path.exists():
        return "indisponível"
    size = path.stat().st_size
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / 1024:.1f} KB"


def _mime_for_path(path: str | Path, fallback: str = "application/octet-stream") -> str:
    suffix = Path(path).suffix.lower()
    if suffix == ".wav":
        return "audio/wav"
    if suffix == ".mp3":
        return "audio/mpeg"
    if suffix in {".m4a", ".aac"}:
        return "audio/mp4"
    if suffix == ".flac":
        return "audio/flac"
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or fallback


def _safe_filename_stem(value: str, default: str = "analysis") -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ._")
    return (cleaned or default)[:90]


def _write_download_file(path: Path, data: str | bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_bytes(data)
    return path


def _is_audio_file(path: str | Path) -> bool:
    return Path(path).suffix.lower().lstrip(".") in AUDIO_EXTENSIONS


def _collect_generated_files(source_result: dict, stems_result: dict, transcript_result: dict) -> list[dict]:
    files: list[dict] = []
    seen_paths: set[str] = set()

    def add_file(label: str, path_value: str | None, kind: str | None = None, role: str = "") -> None:
        if not path_value:
            return
        path = Path(path_value)
        normalized = str(path)
        if normalized in seen_paths:
            return
        seen_paths.add(normalized)
        detected_kind = kind or ("audio" if _is_audio_file(path) else "file")
        files.append(
            {
                "label": label,
                "kind": detected_kind,
                "role": role,
                "path": normalized,
                "mime": _mime_for_path(path, "audio/wav" if detected_kind == "audio" else "application/octet-stream"),
            }
        )

    source_data = source_result.get("data", {}) or {}
    audio_path = source_data.get("audio_path")
    add_file("Mix analisada", audio_path, role="audio_source")

    stems_data = stems_result.get("data", {}) or {}
    stems = stems_data.get("stems", {}) or {}
    for label, key in (
        ("Vocal separado", "vocals"),
        ("Instrumental", "instrumental"),
        ("Mix de fallback", "full_mix"),
    ):
        add_file(label, stems.get(key), "audio", role=key)

    mix_path = stems_data.get("mix_path")
    add_file("Base sem vocal", mix_path, "audio", role="mix_path")

    transcript_path = (transcript_result.get("metadata") or {}).get("transcript_path")
    add_file("Transcrição JSON", transcript_path, "json", role="transcript")
    return files


def render_file_access_card(item: dict, index: int) -> None:
    path = Path(str(item.get("path", "")))
    exists = path.exists()
    label = item.get("label", path.name)
    mime = item.get("mime") or _mime_for_path(path)

    with st.container(border=True):
        cols = st.columns([2, 1, 1])
        cols[0].markdown(f"**{label}**")
        cols[0].caption(str(path))
        cols[1].metric("Tamanho", _file_size_label(path))
        cols[2].metric("Status", "Pronto" if exists else "Ausente")

        if not exists:
            st.warning("Este arquivo foi registrado no relatório, mas não existe mais no disco/cache local.")
            return

        try:
            file_bytes = path.read_bytes()
        except Exception as exc:
            st.error(f"Não consegui ler este arquivo para player/download: {exc}")
            return

        if item.get("kind") == "audio" or _is_audio_file(path):
            st.audio(file_bytes, format=mime)

        st.download_button(
            label=f"Baixar {label}",
            data=file_bytes,
            file_name=path.name,
            mime=mime,
            key=f"download_generated_file_{index}_{path.name}_{path.stat().st_size}",
            on_click="ignore",
            use_container_width=True,
        )


def render_generated_files_tab(source_result: dict, stems_result: dict, transcript_result: dict, lyric_validation_result: dict) -> None:
    st.subheader("Arquivos Gerados")
    st.markdown(
        '<div class="section-intro">Acesso direto ao que a análise produziu ou reaproveitou em cache. Arquivos de áudio podem ser ouvidos aqui mesmo e baixados em seguida.</div>',
        unsafe_allow_html=True,
    )

    status_rows = [
        {
            "Área": "Separação de voz",
            "Status": stems_result.get("mode") or stems_result.get("status", ""),
            "Diagnóstico": " | ".join(stems_result.get("diagnostics", []) or []),
        },
        {
            "Área": "Transcrição",
            "Status": transcript_result.get("mode") or transcript_result.get("status", ""),
            "Diagnóstico": " | ".join(transcript_result.get("diagnostics", []) or []),
        },
        {
            "Área": "Validação de letra",
            "Status": lyric_validation_result.get("mode") or lyric_validation_result.get("status", ""),
            "Diagnóstico": " | ".join(lyric_validation_result.get("diagnostics", []) or []),
        },
    ]
    st.dataframe(status_rows, use_container_width=True, hide_index=True)

    files = _collect_generated_files(source_result, stems_result, transcript_result)
    existing_files = [item for item in files if Path(item["path"]).exists()]
    if existing_files:
        st.markdown("#### Ouvir e baixar")
        for index, item in enumerate(existing_files):
            render_file_access_card(item, index)
    else:
        st.info("Nenhum arquivo extra foi gerado nesta rodada além do relatório.")

    missing_files = [item for item in files if not Path(item["path"]).exists()]
    if missing_files:
        with st.expander("Arquivos registrados, mas indisponíveis no cache", expanded=False):
            st.dataframe(
                [
                    {
                        "Arquivo": item.get("label"),
                        "Caminho": item.get("path"),
                        "Tipo": item.get("kind"),
                    }
                    for item in missing_files
                ],
                use_container_width=True,
                hide_index=True,
            )

    transcript_export = build_transcript_export(transcript_result, lyric_validation_result)
    st.download_button(
        label="Baixar diagnóstico de letra e prosódia",
        data=transcript_export,
        file_name="audioagent_transcricao_diagnostico.txt",
        mime="text/plain",
        key="download_transcript_diagnostic_txt",
        on_click="ignore",
        use_container_width=True,
    )

    with st.expander("Caminhos técnicos", expanded=False):
        st.json({"files": files})


def render_report_downloads(
    report_payload: dict,
    text_report: str,
    specialist_report: dict,
    transcript_text_export: str,
    source_result: dict,
    transcript_result: dict,
) -> None:
    st.subheader("⬇️ Downloads dos Relatórios")
    st.markdown(
        '<div class="section-intro">Os relatórios também ficam gravados em disco para garantir acesso mesmo se o navegador interno bloquear algum download.</div>',
        unsafe_allow_html=True,
    )

    source_title = (source_result.get("data") or {}).get("title") or (source_result.get("data") or {}).get("source_name") or "analysis"
    base_name = _safe_filename_stem(source_title)
    reports_dir = OUTPUT_DIR / "reports"
    json_text = json.dumps(report_payload, ensure_ascii=False, indent=2, default=str)

    report_files = [
        {
            "label": "Relatório Completo (JSON)",
            "path": _write_download_file(reports_dir / f"audioagent_v2_{base_name}.json", json_text),
            "mime": "application/json",
        },
        {
            "label": "Relatório Completo (TXT)",
            "path": _write_download_file(reports_dir / f"audioagent_v2_{base_name}.txt", text_report or ""),
            "mime": "text/plain",
        },
    ]

    if specialist_report.get("markdown"):
        report_files.append(
            {
                "label": "Relatório Especialista (TXT)",
                "path": _write_download_file(
                    reports_dir / f"audioagent_especialista_{base_name}.txt",
                    specialist_report["markdown"],
                ),
                "mime": "text/plain",
            }
        )

    if (transcript_result.get("data") or {}).get("text"):
        report_files.append(
            {
                "label": "Letra & Prosódia (TXT)",
                "path": _write_download_file(
                    reports_dir / f"audioagent_lyrics_{base_name}.txt",
                    transcript_text_export,
                ),
                "mime": "text/plain",
            }
        )

    for index, item in enumerate(report_files):
        path = Path(item["path"])
        with st.container(border=True):
            cols = st.columns([2, 1, 2])
            cols[0].markdown(f"**{item['label']}**")
            cols[0].caption(str(path))
            cols[1].metric("Tamanho", _file_size_label(path))
            cols[2].download_button(
                label=f"Baixar {item['label']}",
                data=path.read_bytes(),
                file_name=path.name,
                mime=item["mime"],
                key=f"download_report_{index}_{path.name}_{path.stat().st_size}",
                on_click="ignore",
                use_container_width=True,
            )

    with st.expander("Se o botão não abrir download no navegador interno", expanded=False):
        st.info("Os arquivos já foram salvos nesta pasta local. Você pode abrir pelo Explorer se o navegador interno bloquear o download.")
        st.code(str(reports_dir), language=None)


def render_lyric_validation_tab(lyric_validation_result: dict) -> None:
    st.subheader("🌐 Verificação de Letra")
    st.markdown(
        '<div class="section-intro">Confirmação online de que a letra ou a faixa encontrada realmente parece existir fora do arquivo enviado.</div>',
        unsafe_allow_html=True,
    )
    if not lyric_validation_result:
        st.info("Nenhuma validação de letra foi executada.")
        return
    st.write(f"Status: `{lyric_validation_result.get('status', '')}` | Modo: `{lyric_validation_result.get('mode', '')}`")
    diagnostics = lyric_validation_result.get("diagnostics", [])
    if diagnostics:
        st.caption(" | ".join(diagnostics))
    if lyric_validation_result.get("data"):
        st.json(lyric_validation_result["data"])


def render_studio_view(
    source_result: dict,
    dsp_result: dict,
    transcript_result: dict,
    lyric_validation_result: dict,
    matcher_result: dict,
    agents_result: dict,
) -> None:
    st.subheader("🎚️ Studio View")
    st.markdown(
        '<div class="section-intro">Painel executivo da análise: o que essa música é, o que foi encontrado e qual o próximo melhor uso criativo.</div>',
        unsafe_allow_html=True,
    )
    source_data = source_result.get("data", {}) or {}
    dsp_data = dsp_result.get("data", {}) or {}
    metrics = dsp_data.get("acoustic_metrics", {}) or {}
    meta = dsp_data.get("metadata", {}) or {}
    transcript_data = transcript_result.get("data", {}) or {}
    lyric_data = lyric_validation_result.get("data", {}) or {}
    candidates = ((matcher_result.get("data") or {}).get("candidates") or [])
    top_candidate = candidates[0] if candidates else {}
    agent_data = agents_result.get("data", {}) or {}
    audit_text = agent_data.get("originality_audit", "") or agent_data.get("auditoria", "")
    score = extract_audit_score(audit_text)
    prompt_preview = shorten_text(extract_style_block(agent_data.get("suno_prompt", ""))[0], 200) if agent_data.get("suno_prompt") else ""

    title = source_data.get("title") or source_data.get("source_name") or "Faixa analisada"
    artist = source_data.get("artist") or "Artista não identificado"
    validation_label = "validada online" if lyric_data.get("validated") else "sem validação online"
    transcript_label = "voz transcrita" if transcript_data.get("text") else "sem letra capturada"

    st.markdown(
        f"""
        <div class="studio-grid">
            <div class="studio-card">
                <h4>{title}</h4>
                <p>{artist}. Esta rodada saiu com {transcript_label}, {validation_label} e leitura estrutural em {len(dsp_data.get('timeline_sections', [])) or 0} blocos.</p>
                <div class="stat-strip">
                    <div class="stat-pill">
                        <div class="stat-pill-label">BPM</div>
                        <div class="stat-pill-value">{round(float(metrics.get('bpm_measured', 0)), 1) if metrics else '—'}</div>
                    </div>
                    <div class="stat-pill">
                        <div class="stat-pill-label">Tonalidade</div>
                        <div class="stat-pill-value">{metrics.get('key_note', '—')} {str(metrics.get('key_mode', '')).capitalize()}</div>
                    </div>
                    <div class="stat-pill">
                        <div class="stat-pill-label">Camelot</div>
                        <div class="stat-pill-value">{metrics.get('camelot_key', '—')}</div>
                    </div>
                    <div class="stat-pill">
                        <div class="stat-pill-label">Duração</div>
                        <div class="stat-pill-value">{int(float(meta.get('duration_seconds', 0)) // 60)}:{int(float(meta.get('duration_seconds', 0)) % 60):02d}</div>
                    </div>
                </div>
            </div>
            <div class="studio-card">
                <h4>Direção rápida</h4>
                <p>Use este resumo para decidir se a faixa está pronta para exploração criativa, mashup, revisão de letra ou refinamento de produção.</p>
                <div class="stat-strip">
                    <div class="stat-pill">
                        <div class="stat-pill-label">Premium</div>
                        <div class="stat-pill-value">{transcript_result.get('mode', '—')}</div>
                    </div>
                    <div class="stat-pill">
                        <div class="stat-pill-label">Auditoria</div>
                        <div class="stat-pill-value">{f'{score}/100' if score is not None else 'pendente'}</div>
                    </div>
                    <div class="stat-pill">
                        <div class="stat-pill-label">Matcher</div>
                        <div class="stat-pill-value">{len(candidates)} candidatos</div>
                    </div>
                    <div class="stat-pill">
                        <div class="stat-pill-label">Prompt</div>
                        <div class="stat-pill-value">{'pronto' if agent_data.get('suno_prompt') else 'pendente'}</div>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if top_candidate:
        st.markdown(
            f"""
            <div class="panel-note">
                Melhor candidato de mashup nesta rodada: <strong>{top_candidate.get('title', '—')}</strong> ·
                {top_candidate.get('artist', '—')} · score {top_candidate.get('compatibility_score', '—')}.
                Ajuste tonal sugerido: {top_candidate.get('pitch_shift_semitones', 0):+} semitons.
            </div>
            """,
            unsafe_allow_html=True,
        )

    if prompt_preview:
        st.markdown("#### Preview do Prompt")
        st.code(prompt_preview, language=None)


def render_matcher_tab(matcher_result: dict, matcher_markdown: str = "") -> None:
    st.subheader("🎧 Mashup Matcher")
    st.markdown(
        '<div class="section-intro">Cruzamento de BPM, tonalidade e energia com um catálogo de referências para sugerir combinações mais fáceis de mixar.</div>',
        unsafe_allow_html=True,
    )
    if matcher_markdown:
        st.markdown(matcher_markdown)
        st.divider()
    matcher_data = matcher_result.get("data", {})
    matcher_meta = matcher_result.get("metadata", {})
    if matcher_meta.get("source_notes"):
        st.caption(f"Fontes de pesquisa informadas: {matcher_meta['source_notes']}")
    candidates = matcher_data.get("candidates", [])
    if not candidates:
        st.info("Nenhum candidato de mashup foi gerado nesta rodada.")
        return
    st.markdown("#### Curadoria rápida")
    cards = []
    for index, candidate in enumerate(candidates, start=1):
        cards.append(
            f"""
            <div class="matcher-card">
                <div class="matcher-rank">#{index}</div>
                <h4>{candidate.get('title', '—')}</h4>
                <p><strong>{candidate.get('artist', '—')}</strong> · {candidate.get('genre', 'Gênero não informado')}</p>
                <div class="matcher-score">Compatibilidade {candidate.get('compatibility_score', '—')}</div>
                <div class="matcher-meta">
                    <span class="matcher-chip">BPM alvo {candidate.get('bpm', '—')}</span>
                    <span class="matcher-chip">Δ BPM {candidate.get('bpm_delta', '—')}</span>
                    <span class="matcher-chip">Camelot {candidate.get('camelot_key', '—')}</span>
                    <span class="matcher-chip">Pitch {candidate.get('pitch_shift_semitones', 0):+} st</span>
                    <span class="matcher-chip">Médios {candidate.get('mid_collision_risk', '—')}</span>
                </div>
                <p>Leitura harmônica: {candidate.get('compatibility_reason', '—')}.</p>
            </div>
            """
        )
    st.markdown('<div class="matcher-stack">' + "".join(cards) + "</div>", unsafe_allow_html=True)
    st.divider()
    st.markdown("#### Tabela técnica")
    st.dataframe(candidates, use_container_width=True, hide_index=True)
    diagnostics = matcher_result.get("diagnostics", [])
    if diagnostics:
        st.caption(" | ".join(diagnostics))


def render_daw_tab(daw_guidance: str) -> None:
    st.subheader("🎛️ DAW & Mix")
    st.markdown(
        '<div class="section-intro">Orientações práticas para levar o resultado da análise para o DAW, com foco em EQ, espaço e transições.</div>',
        unsafe_allow_html=True,
    )
    if daw_guidance:
        st.markdown(daw_guidance)
        with st.expander("📋 Copiar texto bruto"):
            st.code(daw_guidance, language=None)
    else:
        st.info("A matriz de agentes ainda não gerou diretrizes técnicas de Suno/DAW para esta rodada.")


def render_specialist_report_tab(specialist_report: dict) -> None:
    st.subheader("🧠 Relatório Especialista")
    st.markdown(
        '<div class="section-intro">Relatório padronizado no formato das análises de referência: fatos medidos separados de interpretação, hipótese e validação online.</div>',
        unsafe_allow_html=True,
    )
    if not specialist_report:
        st.info("O relatório especialista ainda não foi gerado para esta rodada.")
        return

    identification = specialist_report.get("identification", {}) or {}
    measured = specialist_report.get("measured_data", {}) or {}
    rubric = specialist_report.get("rubric", {}) or {}

    title = identification.get("title", "Faixa analisada")
    artist = identification.get("artist", "Não identificado")
    st.markdown(f"### {title}")
    st.caption(f"Artista: {artist} | Origem: {identification.get('source_type', 'n/d')} | Duração: {identification.get('duration_label', 'n/d')}")

    metric_cols = st.columns(4)
    metric_cols[0].metric("BPM", measured.get("BPM", "n/d"))
    metric_cols[1].metric("Tonalidade", measured.get("Tonalidade provável", "n/d"))
    metric_cols[2].metric("LUFS", measured.get("LUFS integrado", "n/d"))
    metric_cols[3].metric("Camelot", measured.get("Camelot", "n/d"))

    st.markdown("#### Rubrica de leitura")
    st.info(
        f"{rubric.get('family', 'Rubrica geral')} | confiança: {rubric.get('confidence', 'n/d')}. "
        f"Base: {rubric.get('basis', 'n/d')}"
    )

    evidence_summary = specialist_report.get("evidence_summary", {}) or {}
    if evidence_summary:
        st.markdown("#### Matriz de evidências")
        st.dataframe(
            [{"Tipo": key, "Quantidade": value} for key, value in evidence_summary.items()],
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("#### Estrutura por tempo")
    timeline = specialist_report.get("structure_timeline", []) or []
    if timeline:
        st.dataframe(
            [
                {
                    "Tempo": item.get("timestamp"),
                    "Bloco": item.get("detected_label"),
                    "Energia": item.get("energy_label"),
                    "Dominante": item.get("dominant_stem"),
                    "Função": item.get("function"),
                    "Confiança": item.get("confidence"),
                }
                for item in timeline
            ],
            use_container_width=True,
            hide_index=True,
        )
        with st.expander("Mapa de navegação de performance"):
            for item in timeline:
                st.markdown(f"**{item.get('timestamp')} · {item.get('detected_label')}**")
                st.write(item.get("performance_hint", ""))
                st.caption(item.get("production_hint", ""))
    else:
        st.info("Nenhuma seção estrutural foi detectada nesta rodada.")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### DNA musical")
        for item in specialist_report.get("audio_dna", []) or []:
            st.markdown(f"- {item}")
        st.markdown("#### DNA vocal e lírico")
        for item in specialist_report.get("vocal_lyrical_dna", []) or []:
            st.markdown(f"- {item}")
    with col_b:
        st.markdown("#### Produção e mix")
        for item in specialist_report.get("production_dna", []) or []:
            st.markdown(f"- {item}")
        st.markdown("#### Veredito")
        for item in specialist_report.get("verdict", []) or []:
            st.markdown(f"- {item}")

    claims = specialist_report.get("claims", []) or []
    if claims:
        st.markdown("#### Evidências e incertezas")
        st.dataframe(
            [
                {
                    "Tipo": item.get("evidence_label"),
                    "Confiança": item.get("confidence"),
                    "Afirmação": item.get("claim"),
                    "Evidência": item.get("evidence"),
                    "Cautela": item.get("risk"),
                }
                for item in claims
            ],
            use_container_width=True,
            hide_index=True,
        )

    markdown = specialist_report.get("markdown", "")
    if markdown:
        with st.expander("Texto completo do relatório"):
            st.markdown(markdown)
            st.code(markdown, language=None)


def render_history_tab() -> None:
    st.subheader("🗃️ Histórico Técnico")
    st.markdown(
        '<div class="section-intro">Área reservada para rastreabilidade completa das análises já executadas nesta instalação.</div>',
        unsafe_allow_html=True,
    )
    history_entries = load_analysis_history(limit=30)
    if not history_entries:
        st.info("Nenhuma análise foi registrada ainda.")
        return

    selected_run_id = st.selectbox(
        "Selecione uma análise registrada",
        options=[entry["run_id"] for entry in history_entries],
        format_func=lambda run_id: format_history_label(next(item for item in history_entries if item["run_id"] == run_id)),
        key="history_run_id",
    )
    loaded = load_history_run(selected_run_id)
    if not loaded:
        st.warning("Não foi possível carregar este histórico a partir do disco.")
        return

    entry = loaded["entry"]
    payload = loaded["payload"]
    pipeline_data = payload.get("data", {}) or {}
    st.dataframe(
        [
            {"Campo": "Timestamp", "Valor": entry.get("timestamp", "")},
            {"Campo": "Status", "Valor": entry.get("status", "")},
            {"Campo": "Origem", "Valor": entry.get("source_type", "")},
            {"Campo": "Título", "Valor": entry.get("source_title", "")},
            {"Campo": "Artista", "Valor": entry.get("source_artist", "")},
            {"Campo": "Tempo total", "Valor": format_seconds(entry.get("total_elapsed_seconds"))},
            {"Campo": "Gargalo principal", "Valor": STAGE_LABELS.get(entry.get("slowest_stage", ""), entry.get("slowest_stage", ""))},
            {"Campo": "Tempo do gargalo", "Valor": format_seconds(entry.get("slowest_stage_seconds"))},
            {"Campo": "URL", "Valor": entry.get("source_url", "")},
            {"Campo": "Premium", "Valor": "Sim" if entry.get("enable_premium") else "Não"},
            {"Campo": "Agentes IA", "Valor": "Sim" if entry.get("run_agents") else "Não"},
            {"Campo": "LLM", "Valor": f"{entry.get('llm_provider', '')} / {entry.get('llm_model', '')}".strip(" /")},
            {"Campo": "LLM efetiva", "Valor": f"{entry.get('llm_effective_provider', '')} / {entry.get('llm_effective_model', '')}".strip(" /")},
            {"Campo": "Fallback LLM", "Valor": "Sim" if entry.get("llm_fallback_used") else "Não"},
            {"Campo": "JSON", "Valor": entry.get("json_path", "")},
            {"Campo": "TXT", "Valor": entry.get("txt_path", "")},
        ],
        use_container_width=True,
        hide_index=True,
    )

    stage_log = pipeline_data.get("stage_log", []) or payload.get("metadata", {}).get("stage_log", []) or []
    performance = pipeline_data.get("performance", {}) or payload.get("metadata", {}).get("performance", {}) or {}
    if stage_log:
        st.markdown("#### Etapas registradas")
        render_stage_table(
            stage_log,
            performance=performance,
            analysis_context=pipeline_data.get("analysis_context", {}),
            agents_result=pipeline_data.get("agents", {}),
        )

    if entry.get("error"):
        st.markdown("#### Erro registrado")
        st.code(str(entry["error"]), language=None)

    with st.expander("Ver payload completo do histórico", expanded=False):
        st.json(payload)


with st.sidebar:
    st.markdown("## 🎵 AudioAgent")
    st.markdown("**Foundation v2.0**")
    st.divider()

    with st.expander("Como usar a aplicação", expanded=False):
        st.markdown(load_user_guide())

    st.checkbox(
        "Mostrar área técnica reservada",
        key="show_technical_area",
        help="Exibe o histórico persistente e os logs completos das análises nesta instalação.",
    )

    st.subheader("1. Ingestão de Áudio")
    sidebar_audio_url = st.text_input(
        "Ou colar link (YouTube / SoundCloud):",
        key="sidebar_audio_url",
        placeholder="https://youtu.be/...",
    )
    if st.button("Descarregar e Processar Link", use_container_width=True):
        if not sidebar_audio_url.strip():
            st.error("Cole um link válido para iniciar o pré-download.")
        else:
            with st.spinner("A descarregar áudio na melhor qualidade..."):
                try:
                    temp_wav = web_ingest.download_audio_from_url(sidebar_audio_url.strip())
                    st.session_state["prefetched_url"] = sidebar_audio_url.strip()
                    st.session_state["prefetched_audio_path"] = temp_wav
                    st.session_state["main_source_url"] = sidebar_audio_url.strip()
                    st.session_state["auto_run_analysis"] = True
                    st.success("Download concluído. A análise do link será iniciada automaticamente.")
                except Exception as exc:
                    st.error(f"Erro no download: {exc}")

    st.divider()

    st.subheader("🤖 LLM")
    with st.expander("Configuração de LLM", expanded=False):
        provider_options = llm_provider_options()
        provider_labels = {provider: llm_provider_label(provider) for provider in provider_options}
        llm_provider = st.selectbox(
            "Provider",
            options=provider_options,
            key="llm_provider_choice",
            format_func=lambda provider: provider_labels[provider],
            help="Escolha qual backend de LLM executará a matriz de agentes.",
        )

        if st.session_state.get("llm_provider_last") != llm_provider:
            st.session_state["llm_model_input"] = _saved_model_for_provider(llm_provider)
            st.session_state["llm_model_preset"] = _saved_model_for_provider(llm_provider)
            st.session_state["llm_api_key_input"] = resolve_llm_api_key(llm_provider) or _saved_api_key_for_provider(llm_provider)
            st.session_state["llm_provider_last"] = llm_provider

        presets = llm_model_presets(llm_provider)
        preset_options = presets + ["custom"]
        if st.session_state.get("llm_model_preset") not in preset_options:
            st.session_state["llm_model_preset"] = llm_default_model(llm_provider)

        selected_preset = st.selectbox(
            "Modelo sugerido",
            options=preset_options,
            key="llm_model_preset",
            format_func=lambda value: "Customizado" if value == "custom" else value,
            help="Escolha um modelo novo sugerido ou mude para Customizado.",
        )
        if selected_preset != "custom":
            st.session_state["llm_model_input"] = selected_preset

        llm_model = st.text_input(
            "Modelo final",
            key="llm_model_input",
            help="Você pode trocar manualmente por qualquer model ID suportado pelo provider selecionado.",
        )

        st.caption(
            "Defaults estáveis: OpenAI com gpt-4o-mini; Gemini com gemini-2.5-flash. "
            "Modelos mais novos continuam disponíveis na lista."
        )

        env_var_name = llm_env_var(llm_provider)
        st.session_state.setdefault(
            "llm_api_key_input",
            resolve_llm_api_key(llm_provider) or _saved_api_key_for_provider(llm_provider),
        )
        api_key_input = st.text_input(
            f"{provider_labels[llm_provider]} API Key",
            key="llm_api_key_input",
            type="password",
            placeholder=f"{env_var_name}=...",
            help=f"Necessária para rodar a matriz de agentes via {provider_labels[llm_provider]}.",
        )
        if api_key_input:
            os.environ[env_var_name] = api_key_input
        st.caption(f"Variável usada: `{env_var_name}`")
        persist_api_key = st.checkbox(
            "Salvar esta API key localmente neste computador",
            key="persist_api_key_checkbox",
            help="Guarda a chave em arquivo local da aplicação. Use apenas em um computador confiável.",
        )
        if persist_api_key:
            st.caption("A chave será persistida localmente para o provider selecionado.")
        auto_llm_fallback = st.checkbox(
            "Trocar automaticamente para outra LLM configurada se a principal falhar",
            key="auto_llm_fallback_toggle",
            help="Se o provider principal cair por modelo sem acesso, chave inválida, quota ou timeout, a aplicação tenta outra LLM já configurada.",
        )
        fallback_preview = _configured_fallback_preview(llm_provider, llm_model, api_key_input)
        if fallback_preview:
            st.caption("Ordem provável de tentativa: " + " → ".join(fallback_preview))
        elif auto_llm_fallback:
            st.caption("Nenhuma LLM extra configurada foi encontrada para fallback no momento.")

    st.caption("Abra o menu de configuração acima para trocar provider, modelo e chave.")

    with st.expander("Referências musicais e letra online", expanded=False):
        matcher_source_notes = st.text_area(
            "Fontes de pesquisa de músicas",
            key="matcher_source_notes",
            placeholder="Ex.: playlists próprias, blogs, canais, DJs, labels, catálogos internos...",
            help="Essas fontes ficam registradas no relatório e podem orientar o matcher de mashups.",
        )
        st.caption("Essas fontes não baixam músicas sozinhas; elas funcionam como contexto e rastreabilidade da sua pesquisa.")
        lyric_title_hint = st.text_input(
            "Título da música (opcional)",
            key="lyric_title_hint",
            help="Ajuda a validação online da letra quando o arquivo não traz metadados claros.",
        )
        lyric_artist_hint = st.text_input(
            "Artista da música (opcional)",
            key="lyric_artist_hint",
            help="Usado junto com o título para procurar a letra na internet.",
        )
        genius_token = st.text_input(
            "Token da API do Genius (opcional)",
            key="genius_access_token",
            type="password",
            help="Se informado, a aplicação usa a API do Genius como apoio para confirmar a existência da letra ou da faixa.",
        )
        if genius_token:
            os.environ["GENIUS_ACCESS_TOKEN"] = genius_token
        genius_client_id = st.text_input(
            "Genius Client ID (opcional)",
            key="genius_client_id",
            help="Preparação para integração oficial via OAuth ou chamadas diretas à API Genius no futuro.",
        )
        if genius_client_id:
            os.environ["GENIUS_CLIENT_ID"] = genius_client_id
        genius_client_secret = st.text_input(
            "Genius Client Secret (opcional)",
            key="genius_client_secret",
            type="password",
            help="Credencial privada do seu app Genius. Não é necessária para a verificação simples de letra atual.",
        )
        if genius_client_secret:
            os.environ["GENIUS_CLIENT_SECRET"] = genius_client_secret
        st.checkbox(
            "Salvar credenciais do Genius localmente neste computador",
            key="persist_genius_credentials_checkbox",
            help="Guarda token, client ID e client secret em arquivo local da aplicação. Use apenas em um computador confiável.",
        )
        with st.expander("Como conseguir esse token", expanded=False):
            st.markdown(
                """
                1. Acesse [Genius Developers](https://genius.com/developers).
                2. Crie um `API Client`.
                3. Gere um `Client Access Token`.
                4. Cole esse token aqui.

                Neste app, o token é usado hoje para reforçar a verificação online da letra.
                O `Client ID` e o `Client Secret` ficam preparados para uma integração mais oficial no futuro.
                """
            )

    st.divider()
    st.subheader("⚙️ Opções")
    run_agents = st.toggle(
        "Gerar análises com IA",
        key="run_agents_toggle",
        help="Ative para gerar DNA, Blueprint, Prompt Suno, Auditoria e DAW com apoio de LLM.",
    )
    enable_premium = st.toggle(
        "Separação de voz e transcrição avançada",
        key="enable_premium_toggle",
        help="Tenta separar a voz da base e transcrever a letra com marcação de tempo quando este computador suportar.",
    )
    n_sections = st.slider(
        "Nível de detalhe da estrutura",
        min_value=4,
        max_value=16,
        key="n_sections_slider",
        help="Controla o quanto a música será dividida em blocos para a leitura estrutural.",
    )
    st.caption("Mais baixo = visão mais geral da música. Mais alto = leitura mais detalhada das transições e mudanças de energia.")
    st.caption("Separação de voz e transcrição avançada: usa motores extras para tentar isolar a voz e escrever a letra com tempo. Se este computador não suportar, a análise básica continua normalmente.")

    st.divider()
    st.subheader("🧪 Runtime")
    capabilities = runtime_capabilities()
    st.caption(
        f"Status atual: {st.session_state.get('runtime_state', 'online')} | "
        f"Etapa: {st.session_state.get('runtime_stage', 'idle')} | "
        f"Último sinal: {st.session_state.get('runtime_last_seen', '--:--:--')}"
    )
    capability_rows = [{"Feature": key, "Disponível": "Sim" if value else "Não"} for key, value in capabilities.items()]
    st.dataframe(capability_rows, use_container_width=True, hide_index=True)
    st.caption("CPU-first: recursos premium fazem fallback quando indisponíveis.")

    persist_user_preferences(
        llm_provider=llm_provider,
        llm_model=llm_model,
        persist_api_key=persist_api_key,
        api_key=api_key_input,
        auto_llm_fallback=auto_llm_fallback,
        run_agents=run_agents,
        enable_premium=enable_premium,
        n_sections=n_sections,
    )


render_hero_header()
render_copilot_panel(
    llm_provider=llm_provider,
    llm_model=llm_model,
    api_key_input=api_key_input,
    auto_llm_fallback=auto_llm_fallback,
)
st.markdown(
    '<div class="panel-note">Carregue um arquivo ou um link para iniciar uma leitura completa da música: '
    'estrutura, energia, voz, prompt criativo e riscos de originalidade em um único fluxo.</div>',
    unsafe_allow_html=True,
)
st.markdown('<div class="section-intro">Entrada de áudio</div>', unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "Arraste ou selecione um arquivo de áudio",
    type=list(AUDIO_EXTENSIONS),
    label_visibility="collapsed",
)
source_url = st.text_input(
    "Ou cole um link de áudio/vídeo suportado",
    key="main_source_url",
    placeholder="https://www.youtube.com/watch?v=...",
)

if uploaded_file and source_url:
    st.warning("Quando upload e link são informados ao mesmo tempo, o upload local terá prioridade.")
elif st.session_state.get("prefetched_audio_path") and source_url:
    st.caption(f"Link pré-processado e em cache: `{st.session_state['prefetched_audio_path']}`")

render_audio_preview(st.session_state.get("pipeline", {}).get("data", {}) if st.session_state.get("pipeline") else {}, uploaded_file)

can_analyze = uploaded_file is not None or bool(source_url.strip())
status_placeholder = st.empty()
progress_bar = st.progress(0.0, text="Aguardando análise…")
manual_trigger = st.button("🔬 Analisar", type="primary", use_container_width=True, disabled=not can_analyze)
auto_trigger = bool(st.session_state.pop("auto_run_analysis", False))
if auto_trigger and can_analyze:
    st.info("Link preparado pela sidebar. Iniciando análise automaticamente.")

if manual_trigger or (auto_trigger and can_analyze):
    run_analysis_flow(
        uploaded_file=uploaded_file,
        source_url=source_url,
        run_agents=run_agents,
        enable_premium=enable_premium,
        n_sections=n_sections,
        llm_provider=llm_provider,
        llm_model=llm_model,
        api_key_input=api_key_input,
        auto_llm_fallback=auto_llm_fallback,
        status_placeholder=status_placeholder,
        progress_bar=progress_bar,
    )


pipeline_state = st.session_state.get("pipeline")
if pipeline_state:
    pipeline = pipeline_state.get("data", {})
    stage_log = pipeline.get("stage_log", [])
    performance = pipeline.get("performance", {}) or {}
    analysis_context = pipeline.get("analysis_context", {}) or {}
    source_result = pipeline.get("source", {})
    dsp_result = pipeline.get("dsp", {})
    loudness_result = pipeline.get("loudness", {})
    stems_result = pipeline.get("stems", {})
    transcript_result = pipeline.get("transcript", {})
    lyric_validation_result = pipeline.get("lyric_validation", {})
    matcher_result = pipeline.get("matcher", {})
    agents_result = pipeline.get("agents", {})
    specialist_report = pipeline.get("specialist_report", {})
    agent_data = agents_result.get("data", {})
    agent_meta = agents_result.get("metadata", {})

    st.divider()

    if agent_meta.get("llm_provider") and agent_meta.get("llm_model"):
        st.caption(
            f"LLM em uso: {llm_provider_label(agent_meta['llm_provider'])} | modelo `{agent_meta['llm_model']}`"
        )
    if agent_meta.get("llm_fallback_used"):
        st.caption("Fallback automático de LLM foi necessário nesta rodada.")

    tabs_to_render: list[tuple[str, callable]] = [
        (
            "🎚️ Studio View",
            lambda sr=source_result, dr=dsp_result, tr=transcript_result, lr=lyric_validation_result, mr=matcher_result, ar=agents_result: render_studio_view(sr, dr, tr, lr, mr, ar),
        ),
        ("🧭 Pipeline", lambda: render_stage_table(stage_log, performance=performance, analysis_context=analysis_context, agents_result=agents_result)),
    ]

    if st.session_state.get("show_technical_area"):
        tabs_to_render.append(("🗃️ Histórico Técnico", render_history_tab))

    tabs_to_render.append((
        "📁 Arquivos Gerados",
        lambda sr=source_result, st_res=stems_result, tr=transcript_result, lr=lyric_validation_result: render_generated_files_tab(sr, st_res, tr, lr),
    ))

    if specialist_report:
        tabs_to_render.append(("🧠 Relatório Especialista", lambda report=specialist_report: render_specialist_report_tab(report)))

    if dsp_result.get("data"):
        tabs_to_render.append(("📊 Métricas DSP", lambda payload=dsp_result["data"], loud=loudness_result: render_dsp_tab(payload, loud)))

    if transcript_result:
        tabs_to_render.append(("🎤 Letra & Prosódia", lambda tr=transcript_result: render_transcript_tab(tr)))

    if lyric_validation_result:
        tabs_to_render.append(("🌐 Verificação de Letra", lambda lr=lyric_validation_result: render_lyric_validation_tab(lr)))

    if matcher_result:
        tabs_to_render.append((
            "🎧 Mashup Matcher",
            lambda mr=matcher_result, md=agent_data.get("mashup_matcher", ""): render_matcher_tab(mr, md),
        ))

    if agent_data.get("dna"):
        tabs_to_render.append(
            ("🧬 DNA Instrumental", lambda text=agent_data.get("dna", ""): render_markdown_result(
                "🧬 DNA Instrumental",
                text,
                "Ative os agentes para gerar o DNA Instrumental.",
            ))
        )

    if agent_data.get("lyrics_dna"):
        tabs_to_render.append(
            ("🎙️ DNA Lírico", lambda text=agent_data.get("lyrics_dna", ""): render_markdown_result(
                "🎙️ DNA Lírico",
                text,
                "Nenhum DNA lírico foi produzido nesta rodada.",
            ))
        )

    if agent_data.get("blueprint"):
        tabs_to_render.append(
            ("🏗️ Blueprint", lambda text=agent_data.get("blueprint", ""): render_markdown_result(
                "🏗️ Blueprint Estrutural",
                text,
                "Ative os agentes para gerar o blueprint.",
            ))
        )

    if agent_data.get("suno_prompt"):
        tabs_to_render.append(("📝 Prompt Suno", lambda text=agent_data.get("suno_prompt", ""): render_prompt_tab(text)))

    if agent_data.get("originality_audit"):
        tabs_to_render.append(
            ("🛡️ Auditoria", lambda text=agent_data.get("originality_audit", ""), meta=agents_result.get("metadata", {}): render_audit_tab(text, meta))
        )

    if agent_data.get("daw_guidance") or agents_result.get("status") == "success":
        tabs_to_render.append(("🎛️ DAW & Mix", lambda text=agent_data.get("daw_guidance", ""): render_daw_tab(text)))

    tab_labels = [label for label, _ in tabs_to_render]
    for tab, (_, renderer) in zip(st.tabs(tab_labels), tabs_to_render):
        with tab:
            renderer()

    st.divider()
    report_payload = {
        "analysis_context": pipeline.get("analysis_context", {}),
        "source": source_result,
        "dsp": dsp_result,
        "loudness": loudness_result,
        "stems": stems_result,
        "transcript": transcript_result,
        "lyric_validation": lyric_validation_result,
        "matcher": matcher_result,
        "agents": agents_result,
        "specialist_report": specialist_report,
        "stage_log": stage_log,
        "performance": performance,
        "warnings": pipeline.get("warnings", []),
    }
    text_report = pipeline.get("text_report", "")
    transcript_text_export = build_transcript_export(transcript_result, lyric_validation_result)
    render_report_downloads(
        report_payload=report_payload,
        text_report=text_report,
        specialist_report=specialist_report,
        transcript_text_export=transcript_text_export,
        source_result=source_result,
        transcript_result=transcript_result,
    )
elif st.session_state.get("show_technical_area"):
    st.divider()
    render_history_tab()
