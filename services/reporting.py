from __future__ import annotations

import json
from typing import Any


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, indent=2)


def generate_text_report(report_payload: dict[str, Any]) -> str:
    lines: list[str] = []

    source = report_payload.get("source", {})
    source_data = source.get("data", {})
    analysis_context = report_payload.get("analysis_context", {})
    dsp = report_payload.get("dsp", {}).get("data", {})
    loudness = report_payload.get("loudness", {})
    transcript = report_payload.get("transcript", {})
    lyric_validation = report_payload.get("lyric_validation", {})
    matcher = report_payload.get("matcher", {})
    agents = report_payload.get("agents", {})
    specialist_report = report_payload.get("specialist_report", {})
    stage_log = report_payload.get("stage_log", [])
    performance = report_payload.get("performance", {})
    warnings = report_payload.get("warnings", [])

    lines.append("AudioAgent Report")
    lines.append("=" * 80)
    lines.append("")

    lines.append("Source")
    lines.append("-" * 80)
    lines.append(f"Type: {source_data.get('source_type', '')}")
    lines.append(f"Name/Title: {source_data.get('title') or source_data.get('source_name') or ''}")
    lines.append(f"Artist: {source_data.get('artist', '')}")
    lines.append(f"Audio path: {source_data.get('audio_path', '')}")
    lines.append("")

    if specialist_report.get("markdown"):
        lines.append(specialist_report["markdown"].strip())
        lines.append("")

    if analysis_context:
        lines.append("Analysis Context")
        lines.append("-" * 80)
        lines.append(_stringify(analysis_context))
        lines.append("")

    if warnings:
        lines.append("Warnings")
        lines.append("-" * 80)
        for item in warnings:
            lines.append(f"- {item}")
        lines.append("")

    if performance:
        lines.append("Performance")
        lines.append("-" * 80)
        lines.append(f"Total elapsed: {performance.get('total_elapsed_seconds', '')} s")
        lines.append(f"Slowest stage: {performance.get('slowest_stage', '')}")
        lines.append(f"Slowest stage time: {performance.get('slowest_stage_seconds', '')} s")
        for item in performance.get("stage_timings", []):
            lines.append(
                f"- {item.get('stage', '')}: {item.get('elapsed_seconds', '')} s"
                f" [{item.get('status', '')}] {item.get('message', '')}"
            )
        lines.append("")

    if dsp:
        meta = dsp.get("metadata", {})
        metrics = dsp.get("acoustic_metrics", {})
        lines.append("DSP Summary")
        lines.append("-" * 80)
        lines.append(f"Duration: {meta.get('duration_seconds', '')} s")
        lines.append(f"BPM: {metrics.get('bpm_measured', '')}")
        lines.append(f"Key: {metrics.get('key_note', '')} {metrics.get('key_mode', '')}")
        lines.append(f"Camelot: {metrics.get('camelot_key', '')}")
        lines.append("")

    loudness_data = loudness.get("data", {}) if isinstance(loudness, dict) else {}
    if loudness_data:
        lines.append("Loudness & Dynamics")
        lines.append("-" * 80)
        lines.append(f"Method: {loudness_data.get('method', '')}")
        lines.append(f"Confidence: {loudness_data.get('confidence', '')}")
        if "integrated_lufs" in loudness_data:
            lines.append(f"Integrated LUFS: {loudness_data.get('integrated_lufs')}")
        lines.append(f"RMS dBFS: {loudness_data.get('rms_loudness_dbfs', '')}")
        lines.append(f"Sample Peak dBFS: {loudness_data.get('sample_peak_dbfs', '')}")
        lines.append(f"Loudness Range Proxy LU: {loudness_data.get('loudness_range_proxy_lu', '')}")
        lines.append(f"Crest Factor dB: {loudness_data.get('crest_factor_db', '')}")
        lines.append(f"Stereo Correlation: {loudness_data.get('stereo_correlation', '')}")
        if loudness.get("diagnostics"):
            lines.append("Diagnostics: " + " | ".join(loudness["diagnostics"]))
        lines.append("")

    transcript_data = transcript.get("data", {})
    lines.append("Lyrics & Prosody")
    lines.append("-" * 80)
    lines.append(f"Transcript mode: {transcript.get('mode', '')}")
    if transcript_data.get("alignment_status"):
        lines.append(f"Alignment: {transcript_data.get('alignment_status')}")
    if transcript_data.get("transcription_confidence"):
        lines.append(f"Transcription confidence: {transcript_data.get('transcription_confidence')}")
    lines.append(f"Transcript available: {'yes' if transcript_data.get('text') else 'no'}")
    if transcript.get("diagnostics"):
        lines.append("Diagnostics: " + " | ".join(transcript["diagnostics"]))
    if transcript_data.get("text"):
        lines.append("")
        lines.append(transcript_data["text"])
    elif transcript.get("mode") == "empty":
        lines.append("No usable vocal text was detected by the local transcription engine.")
    lines.append("")

    if lyric_validation:
        lines.append("Lyrics Verification")
        lines.append("-" * 80)
        lines.append(f"Status: {lyric_validation.get('status', '')}")
        lines.append(f"Mode: {lyric_validation.get('mode', '')}")
        if lyric_validation.get("diagnostics"):
            lines.append("Diagnostics: " + " | ".join(lyric_validation["diagnostics"]))
        validation_data = lyric_validation.get("data", {})
        if validation_data:
            lines.append(_stringify(validation_data))
        lines.append("")

    lines.append("Mashup Matcher")
    lines.append("-" * 80)
    matcher_data = matcher.get("data", {})
    matcher_meta = matcher.get("metadata", {})
    if matcher.get("diagnostics"):
        lines.append("Diagnostics: " + " | ".join(matcher["diagnostics"]))
    if matcher_meta.get("source_notes"):
        lines.append("Source Notes: " + matcher_meta["source_notes"])
    if matcher_data:
        lines.append(_stringify(matcher_data))
    lines.append("")

    lines.append("Agent Outputs")
    lines.append("-" * 80)
    agent_data = agents.get("data", {})
    for key in (
        "dna",
        "lyrics_dna",
        "blueprint",
        "suno_prompt",
        "originality_audit",
        "daw_guidance",
        "mashup_matcher",
    ):
        if agent_data.get(key):
            lines.append(key.upper())
            lines.append(_stringify(agent_data[key]))
            lines.append("")

    lines.append("Stage Log")
    lines.append("-" * 80)
    for item in stage_log:
        elapsed = item.get("elapsed_seconds")
        elapsed_label = f" ({elapsed}s)" if elapsed is not None else ""
        lines.append(f"[{item.get('stage')}] {item.get('status')}{elapsed_label}: {item.get('message')}")

    return "\n".join(lines).strip() + "\n"
