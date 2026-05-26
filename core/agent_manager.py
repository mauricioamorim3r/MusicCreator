"""
agent_manager.py
────────────────
Orquestrador da matriz de agentes do AudioAgent v2 com contexto modular
e loop de auto-correção limitado pelo score de auditoria.
"""

from __future__ import annotations

import json
import re
from typing import Any

from services.models import AgentResults
from services.llm_backends import call_llm_with_fallback, normalize_provider, resolve_provider_candidates


def _call_agent(
    llm_candidates: list[dict[str, str]],
    system_prompt: str,
    user_message: str,
    stage_name: str,
    llm_call_log: list[dict[str, Any]],
    diagnostics: list[str],
    max_tokens: int = 2048,
) -> str:
    result = call_llm_with_fallback(
        candidates=llm_candidates,
        system_prompt=system_prompt,
        user_message=user_message,
        max_tokens=max_tokens,
    )
    llm_call_log.append(
        {
            "stage": stage_name,
            "provider": result["provider"],
            "model": result["model"],
            "fallback_used": result["fallback_used"],
            "attempts": result["attempts"],
        }
    )
    if result["fallback_used"]:
        success_attempt = next((item for item in result["attempts"] if item.get("status") == "success"), None)
        failed_labels = [
            f"{item['label']} ({item['model']})"
            for item in result["attempts"]
            if item.get("status") == "failure"
        ]
        diagnostics.append(
            "Fallback automático de LLM acionado em "
            f"{stage_name}: {' -> '.join(failed_labels)} "
            f"falhou; usando {success_attempt['label']} ({success_attempt['model']})."
        )
    return result["text"]


def _strip_ui_keys(payload: dict) -> dict:
    return {k: v for k, v in payload.items() if not k.startswith("_")}


def _fmt(obj: Any) -> str:
    def normalize(value: Any) -> Any:
        if hasattr(value, "item") and callable(value.item):
            try:
                return value.item()
            except Exception:
                pass
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [normalize(item) for item in value]
        if isinstance(value, tuple):
            return [normalize(item) for item in value]
        return value

    return json.dumps(normalize(obj), ensure_ascii=False, indent=2)


def extract_score(text: str) -> int | None:
    match = re.search(r"Score de Originalidade:\s*\[?(\d+)", text, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d+)\s*/\s*100", text)
    return int(match.group(1)) if match else None


def _get_skill(skills: dict, *keys: str) -> dict:
    for key in keys:
        if key in skills:
            return skills[key]
    raise KeyError(f"Nenhuma skill encontrada para as chaves: {', '.join(keys)}")


def _extract_retry_directive(audit_text: str, score: int | None) -> str:
    section_match = re.search(
        r"## GATILHO DE RE-PROMPTING(.*?)(?:\n## |\Z)",
        audit_text,
        flags=re.DOTALL,
    )
    if section_match:
        return section_match.group(1).strip()
    if score is not None:
        return (
            f"O score de originalidade ficou em {score}/100. "
            "Reescreva o Style Prompt reduzindo semelhanças, reforçando exclusões e "
            "diversificando harmonia, arranjo e timbres."
        )
    return "Reescreva o Style Prompt com foco em maior originalidade e menor previsibilidade."


def _safe_transcript_context(context: dict) -> dict:
    transcript_result = context.get("transcript_result", {}) or {}
    transcript_data = transcript_result.get("data", {}) or {}
    words = transcript_data.get("words", [])[:80]
    return {
        "text": transcript_data.get("text", ""),
        "language": transcript_data.get("language"),
        "segments": transcript_data.get("segments", [])[:20],
        "words": words,
    }


def _build_dsp_summary(dsp_payload: dict) -> dict[str, Any]:
    metadata = dsp_payload.get("metadata", {}) or {}
    metrics = dsp_payload.get("acoustic_metrics", {}) or {}
    sections = list(dsp_payload.get("timeline_sections", []) or [])
    energy_curve = dsp_payload.get("_energy_curve", {}) or {}

    section_digest = []
    for section in sections[:8]:
        section_digest.append(
            {
                "label": section.get("section_label"),
                "start": section.get("timestamp_start"),
                "end": section.get("timestamp_end"),
                "energy": section.get("relative_energy_score"),
                "dominant_stem": section.get("dominant_stem"),
            }
        )

    section_peaks = sorted(
        [
            {
                "label": section.get("section_label"),
                "energy": section.get("relative_energy_score"),
                "dominant_stem": section.get("dominant_stem"),
            }
            for section in sections
        ],
        key=lambda item: item.get("energy") or 0,
        reverse=True,
    )[:3]

    return {
        "track_profile": {
            "duration_seconds": metadata.get("duration_seconds"),
            "sample_rate": metadata.get("sample_rate"),
            "bpm_measured": metrics.get("bpm_measured"),
            "key_note": metrics.get("key_note"),
            "key_mode": metrics.get("key_mode"),
            "camelot_key": metrics.get("camelot_key"),
        },
        "spectral_profile": {
            "low_energy_db": ((metrics.get("frequency_distribution") or {}).get("low_energy_db")),
            "mid_energy_db": ((metrics.get("frequency_distribution") or {}).get("mid_energy_db")),
            "high_energy_db": ((metrics.get("frequency_distribution") or {}).get("high_energy_db")),
            "spectral_bandwidth_hz": metrics.get("spectral_bandwidth_hz"),
            "spectral_flatness": metrics.get("spectral_flatness"),
            "zero_crossing_rate": metrics.get("zero_crossing_rate"),
        },
        "section_digest": section_digest,
        "top_energy_sections": section_peaks,
        "energy_curve_samples": len(energy_curve.get("times", []) or []),
    }


def run_pipeline(
    context: dict,
    skills: dict,
    progress_callback=None,
    retry_threshold: int = 70,
    max_attempts: int = 3,
    llm_options: dict[str, Any] | None = None,
) -> AgentResults:
    def progress(step: int, label: str) -> None:
        if progress_callback:
            progress_callback(step, label)

    dsp_payload = context["dsp_payload"] if "dsp_payload" in context else context
    requested_provider = normalize_provider(str((llm_options or {}).get("provider") or "anthropic"))
    requested_model = str((llm_options or {}).get("model") or "")
    llm_candidates = resolve_provider_candidates(llm_options)
    if not llm_candidates:
        raise RuntimeError(
            "Nenhuma LLM configurada com API key disponível. "
            "Cadastre ao menos uma chave válida na seção Configuração de LLM."
        )
    clean = _strip_ui_keys(dsp_payload)
    dsp_summary = _build_dsp_summary(dsp_payload)
    transcript_context = _safe_transcript_context(context)
    matcher_candidates = ((context.get("matcher_result") or {}).get("data") or {}).get("candidates", [])
    matcher_metadata = ((context.get("matcher_result") or {}).get("metadata") or {})
    stems_result = context.get("stems_result", {}) or {}
    lyric_validation = context.get("lyric_validation_result", {}) or {}

    results: dict[str, Any] = {}
    diagnostics: list[str] = []
    llm_call_log: list[dict[str, Any]] = []

    progress(1, "Skill 1/4 — Extração de DNA Instrumental…")
    msg1 = (
        "Analise o payload DSP abaixo e produza o perfil completo de DNA instrumental. "
        "Seja concreto, técnico e específico; evite generalidades. "
        "Inclua observações numéricas, hipóteses de timbre, dinâmica, densidade e limitações quando necessário.\n\n"
        + _fmt(
            {
                "dsp_summary": dsp_summary,
                "timeline_sections": clean.get("timeline_sections", []),
                "stems_context": {
                    "mode": stems_result.get("mode"),
                    "diagnostics": stems_result.get("diagnostics", []),
                    "available_stems": list(((stems_result.get("data") or {}).get("stems") or {}).keys()),
                },
            }
        )
    )
    results["dna"] = _call_agent(
        llm_candidates,
        _get_skill(skills, "skill_1_dna_extractor")["system_prompt"],
        msg1,
        "dna",
        llm_call_log,
        diagnostics,
    )

    lyrics_dna = ""
    lyrics_skill = None
    for key in ("skill_1_5_text_lyrics_dna_extractor", "skill_5_lyrics_dna"):
        if key in skills:
            lyrics_skill = skills[key]
            break
    if transcript_context.get("text") and lyrics_skill:
        progress(2, "Skill 1.5 — Extração de DNA Lírico e Prosódico…")
        msg15 = (
            "Com base na transcrição alinhada e no payload DSP abaixo, "
            "extraia o DNA lírico em JSON estruturado:\n\n"
            + _fmt({"dsp_summary": dsp_summary, "transcript": transcript_context})
        )
        lyrics_dna = _call_agent(
            llm_candidates,
            lyrics_skill["system_prompt"],
            msg15,
            "lyrics_dna",
            llm_call_log,
            diagnostics,
            max_tokens=1400,
        )
        results["lyrics_dna"] = lyrics_dna
    else:
        diagnostics.append("DNA lírico não foi gerado por ausência de transcrição alinhada.")

    progress(3, "Skill 2/4 — Construindo Blueprint Estrutural…")
    ctx2 = {**clean, "dna_analysis": results["dna"]}
    if lyrics_dna:
        ctx2["lyrics_dna"] = lyrics_dna
    msg2 = (
        "Com base nos dados DSP, DNA Instrumental e contexto lírico opcional abaixo, "
        "construa um Blueprint Estrutural detalhado e útil para produção real. "
        "Evite texto genérico; descreva mudanças audíveis, automações, densidade e uso provável de espaço espectral.\n\n"
        + _fmt(
            {
                **ctx2,
                "dsp_summary": dsp_summary,
                "stems_context": {
                    "mode": stems_result.get("mode"),
                    "diagnostics": stems_result.get("diagnostics", []),
                },
                "lyric_validation": lyric_validation.get("data", {}),
            }
        )
    )
    results["blueprint"] = _call_agent(
        llm_candidates,
        _get_skill(skills, "skill_2_blueprint_builder")["system_prompt"],
        msg2,
        "blueprint",
        llm_call_log,
        diagnostics,
    )

    if matcher_candidates:
        results["mashup_candidates"] = matcher_candidates
        matcher_skill = None
        for key in ("skill_2_5_mashup_candidate_matcher", "skill_6_mashup_matcher"):
            if key in skills:
                matcher_skill = skills[key]
                break
        if matcher_skill:
            progress(4, "Skill 2.5 — Curadoria de candidatas para mashup…")
            msg25 = (
                "Com base no BPM, chave Camelot e lista de candidatas abaixo, "
                "produza a leitura curatorial de mashup:\n\n"
                + _fmt(
                    {
                        "dsp_summary": dsp_summary,
                        "candidates": matcher_candidates,
                        "source_notes": matcher_metadata.get("source_notes", ""),
                    }
                )
            )
            results["mashup_matcher"] = _call_agent(
                llm_candidates,
                matcher_skill["system_prompt"],
                msg25,
                "mashup_matcher",
                llm_call_log,
                diagnostics,
                max_tokens=1200,
            )

    best_attempt: dict[str, Any] | None = None
    retry_feedback = ""
    attempts: list[dict[str, Any]] = []

    for attempt in range(1, max_attempts + 1):
        progress(5, f"Skill 3/4 — Gerando Suno Prompt (tentativa {attempt}/{max_attempts})…")
        ctx3 = {**ctx2, "structural_blueprint": results["blueprint"]}
        if matcher_candidates:
            ctx3["mashup_candidates"] = matcher_candidates
        if retry_feedback:
            ctx3["retry_feedback"] = retry_feedback

        msg3_prefix = (
            "Com base em todos os dados abaixo, gere o Style Prompt otimizado para Suno AI:\n\n"
            if not retry_feedback
            else "Refaça o Style Prompt com base no feedback crítico de auditoria abaixo:\n\n"
        )
        msg3 = msg3_prefix + _fmt(ctx3)
        if retry_feedback:
            msg3 = (
                f"O prompt anterior foi rejeitado pela auditoria autoral. "
                f"Feedback crítico: {retry_feedback}\n\n"
                "Crie uma nova versão do Style Prompt garantindo máxima originalidade, "
                "alterando timbres e afastando a estrutura melódica da referência.\n\n"
                + _fmt(ctx3)
            )
        results["suno_prompt"] = _call_agent(
            llm_candidates,
            _get_skill(skills, "skill_3_prompt_optimizer")["system_prompt"],
            msg3,
            "suno_prompt",
            llm_call_log,
            diagnostics,
            max_tokens=1500,
        )

        progress(6, f"Skill 4/4 — Auditoria de Originalidade (tentativa {attempt}/{max_attempts})…")
        ctx4 = {**ctx3, "generated_suno_prompt": results["suno_prompt"]}
        audit = _call_agent(
            llm_candidates,
            _get_skill(skills, "skill_4_originality_auditor")["system_prompt"],
            "Realize a auditoria completa de originalidade com base em todo o material abaixo:\n\n"
            + _fmt(ctx4),
            "originality_audit",
            llm_call_log,
            diagnostics,
            max_tokens=2048,
        )
        score = extract_score(audit)
        attempt_snapshot = {
            "attempt": attempt,
            "score": score,
            "suno_prompt": results["suno_prompt"],
            "originality_audit": audit,
        }
        attempts.append(attempt_snapshot)

        if best_attempt is None or (score or -1) > (best_attempt.get("score") or -1):
            best_attempt = attempt_snapshot

        if score is None or score >= retry_threshold or attempt == max_attempts:
            break

        retry_feedback = _extract_retry_directive(audit, score)
        diagnostics.append(
            f"Tentativa {attempt} ficou em {score}/100; auto-correção acionada para a próxima rodada."
        )

    if best_attempt is None:
        raise RuntimeError("A matriz de agentes não produziu nenhuma tentativa válida.")

    results["suno_prompt"] = best_attempt["suno_prompt"]
    results["originality_audit"] = best_attempt["originality_audit"]
    results["auditoria"] = best_attempt["originality_audit"]
    results["tentativas_loop"] = len(attempts)
    results["score_final"] = best_attempt.get("score")

    daw_skill = None
    for key in ("skill_3_5_suno_settings_daw_director", "skill_7_daw_director"):
        if key in skills:
            daw_skill = skills[key]
            break

    if daw_skill:
        progress(7, "Skill 3.5 — Gerando diretrizes de Suno e DAW…")
        msg35 = (
            "Com base no payload DSP, no blueprint e no prompt final abaixo, gere um guia técnico "
            "de sliders do Suno e ações em DAW:\n\n"
            + _fmt(
                {
                    "dsp_payload": clean,
                    "dsp_summary": dsp_summary,
                    "blueprint": results["blueprint"],
                    "final_suno_prompt": results["suno_prompt"],
                }
            )
        )
        results["daw_guidance"] = _call_agent(
            llm_candidates,
            daw_skill["system_prompt"],
            msg35,
            "daw_guidance",
            llm_call_log,
            diagnostics,
            max_tokens=1400,
        )
        results["daw_director"] = results["daw_guidance"]

    progress(8, "Pipeline de agentes concluído.")
    score = best_attempt.get("score")
    effective_call = next((item for item in reversed(llm_call_log) if item.get("provider")), {})
    return AgentResults(
        status="success",
        mode="completed",
        data=results,
        diagnostics=diagnostics or ["Matriz de agentes executada com sucesso."],
        metadata={
            "llm_provider": effective_call.get("provider", requested_provider),
            "llm_model": effective_call.get("model", requested_model or llm_candidates[0]["model"]),
            "llm_requested_provider": requested_provider,
            "llm_requested_model": requested_model or llm_candidates[0]["model"],
            "llm_fallback_used": any(item.get("fallback_used") for item in llm_call_log),
            "llm_candidates": [
                {"provider": item["provider"], "model": item["model"]}
                for item in llm_candidates
            ],
            "llm_call_history": llm_call_log,
            "audit_score": score,
            "retry_threshold": retry_threshold,
            "attempt_count": len(attempts),
            "retry_history": attempts,
            "best_attempt": best_attempt["attempt"],
        },
    )
