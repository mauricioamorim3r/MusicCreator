from __future__ import annotations

import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Callable

from core.agent_manager import run_pipeline as run_agent_pipeline
from core.dsp_engine import analyze_audio
from core.matcher import find_mashup_candidates
from services.config import DSP_CACHE_DIR, UPLOAD_CACHE_DIR, ensure_runtime_dirs
from services.lyrics_verifier import verify_transcript_exists
from services.loudness_analyzer import analyze_loudness
from services.models import IngestResult, PipelineResult, ResultEnvelope
from services.reporting import generate_text_report
from services.specialist_report import generate_specialist_report
from services.vocals_processor import separate_vocals, transcribe_vocals
from services.web_ingest import ingest_audio

StageCallback = Callable[[str, str, str], None] | None


def _emit(callback: StageCallback, stage: str, status: str, message: str) -> None:
    if callback:
        callback(stage, status, message)


def _final_status(status: str) -> bool:
    return status != "running"


def _build_performance_report(stage_metrics: dict[str, dict], pipeline_started_at: float) -> dict:
    ordered = []
    for stage, item in stage_metrics.items():
        ordered.append(
            {
                "stage": stage,
                "status": item.get("status"),
                "elapsed_seconds": round(float(item.get("elapsed_seconds", 0.0)), 2),
                "message": item.get("message", ""),
            }
        )
    ordered.sort(key=lambda item: item["elapsed_seconds"], reverse=True)
    total_elapsed = round(perf_counter() - pipeline_started_at, 2)
    slowest = ordered[0] if ordered else {}
    return {
        "total_elapsed_seconds": total_elapsed,
        "slowest_stage": slowest.get("stage"),
        "slowest_stage_seconds": slowest.get("elapsed_seconds", 0.0),
        "stage_timings": ordered,
    }


def _json_safe(value):
    if hasattr(value, "item") and callable(value.item):
        try:
            return value.item()
        except Exception:
            pass
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value


def ingest_uploaded_audio(file_name: str, file_bytes: bytes) -> IngestResult:
    ensure_runtime_dirs()
    content_hash = hashlib.sha256(file_bytes).hexdigest()[:16]
    suffix = Path(file_name).suffix or ".wav"
    target_path = UPLOAD_CACHE_DIR / f"{Path(file_name).stem}_{content_hash}{suffix}"

    if not target_path.exists():
        target_path.write_bytes(file_bytes)
        cache_hit = False
        mode = "uploaded"
        diagnostics = ["Arquivo local salvo no cache de uploads."]
    else:
        cache_hit = True
        mode = "cached"
        diagnostics = ["Arquivo local reaproveitado do cache de uploads."]

    return IngestResult(
        status="success",
        mode=mode,
        data={
            "audio_path": str(target_path),
            "source_type": "upload",
            "source_name": file_name,
            "title": Path(file_name).stem,
        },
        diagnostics=diagnostics,
        metadata={"cache_hit": cache_hit, "content_hash": content_hash},
    )


def _dsp_cache_key(audio_path: str, n_sections: int) -> str:
    path = Path(audio_path)
    stat = path.stat()
    fingerprint = f"{path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}|{n_sections}"
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:16]


def analyze_audio_cached(audio_path: str, n_sections: int) -> ResultEnvelope:
    ensure_runtime_dirs()
    cache_key = _dsp_cache_key(audio_path, n_sections)
    cache_path = DSP_CACHE_DIR / f"{cache_key}.json"
    if cache_path.exists():
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        return ResultEnvelope(
            status="success",
            mode="cached",
            data=payload,
            diagnostics=["Análise DSP reaproveitada do cache local."],
            metadata={"cache_key": cache_key, "cache_path": str(cache_path)},
        )

    payload = analyze_audio(audio_path, n_sections=n_sections)
    cache_path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False), encoding="utf-8")
    return ResultEnvelope(
        status="success",
        mode="computed",
        data=_json_safe(payload),
        diagnostics=["Análise DSP concluída com sucesso."],
        metadata={"cache_key": cache_key, "cache_path": str(cache_path)},
    )


def run_audio_pipeline(
    *,
    upload_name: str | None = None,
    upload_bytes: bytes | None = None,
    source_url: str | None = None,
    n_sections: int = 8,
    run_agents: bool = True,
    enable_premium: bool = False,
    skills: dict | None = None,
    agent_options: dict | None = None,
    matcher_sources: str = "",
    lyric_verification_options: dict | None = None,
    progress_callback: StageCallback = None,
) -> PipelineResult:
    ensure_runtime_dirs()
    stage_log: list[dict[str, str]] = []
    stage_metrics: dict[str, dict] = {}
    pipeline_started_at = perf_counter()

    def log(stage: str, status: str, message: str) -> None:
        metric = stage_metrics.setdefault(stage, {"started_at": perf_counter()})
        now = perf_counter()
        if metric.get("started_at") is None:
            metric["started_at"] = now
        metric["status"] = status
        metric["message"] = message
        entry = {"stage": stage, "status": status, "message": message}
        if _final_status(status):
            metric["elapsed_seconds"] = round(now - float(metric["started_at"]), 2)
            entry["elapsed_seconds"] = metric["elapsed_seconds"]
        stage_log.append(entry)
        _emit(progress_callback, stage, status, message)

    source_result: IngestResult
    if source_url:
        log("ingest", "running", "Baixando e normalizando áudio do link...")
        source_result = ingest_audio(source_url)
    elif upload_name and upload_bytes is not None:
        log("ingest", "running", "Persistindo upload local no cache...")
        source_result = ingest_uploaded_audio(upload_name, upload_bytes)
    else:
        return PipelineResult(
            status="failure",
            error="Nenhuma fonte de áudio foi fornecida.",
            diagnostics=["Informe um upload de arquivo ou uma URL suportada."],
            metadata={
                "stage_log": stage_log,
                "performance": _build_performance_report(stage_metrics, pipeline_started_at),
            },
        )

    log("ingest", source_result.status, source_result.error or source_result.diagnostics[0])
    if not source_result.ok:
        return PipelineResult(
            status="failure",
            data={"source": source_result.to_dict()},
            error=source_result.error,
            diagnostics=source_result.diagnostics,
            metadata={
                "stage_log": stage_log,
                "performance": _build_performance_report(stage_metrics, pipeline_started_at),
            },
        )

    audio_path = source_result.data["audio_path"]
    source_title = str(source_result.data.get("title") or source_result.data.get("source_name") or "")

    log("dsp", "running", "Analisando áudio com Librosa...")
    try:
        dsp_result = analyze_audio_cached(audio_path, n_sections=n_sections)
        payload = dsp_result.data
        if dsp_result.mode == "cached":
            log("dsp", "success", "Métricas acústicas reaproveitadas do cache DSP.")
        else:
            log("dsp", "success", "Métricas acústicas, seções e curva de energia prontas.")
    except Exception as exc:
        log("dsp", "failure", f"Falha na análise DSP: {exc}")
        return PipelineResult(
            status="failure",
            data={"source": source_result.to_dict()},
            mode="failed",
            metadata={
                "stage_log": stage_log,
                "performance": _build_performance_report(stage_metrics, pipeline_started_at),
            },
            error=f"Falha na análise DSP: {exc}",
            diagnostics=[str(exc)],
        )

    log("loudness", "running", "Calculando loudness, pico e faixa dinâmica...")
    loudness_result = analyze_loudness(audio_path)
    log(
        "loudness",
        loudness_result.mode or loudness_result.status,
        loudness_result.diagnostics[0] if loudness_result.diagnostics else "Loudness concluido.",
    )

    if enable_premium:
        log("stems", "running", "Tentando separar vocais com Demucs...")
        stems_result = separate_vocals(audio_path)
        log("stems", stems_result.mode or stems_result.status, stems_result.diagnostics[0])

        log("transcription", "running", "Tentando transcrição alinhada com WhisperX...")
        transcript_result = transcribe_vocals(stems_result.data.get("vocals_path", audio_path))
        log("transcription", transcript_result.mode or transcript_result.status, transcript_result.diagnostics[0])
    else:
        stems_result = ResultEnvelope(
            status="success",
            mode="skipped",
            data={"vocals_path": audio_path, "mix_path": audio_path, "stems": {"full_mix": audio_path}},
            diagnostics=["Análise premium desativada; separação de stems ignorada."],
        )
        transcript_result = ResultEnvelope(
            status="success",
            mode="skipped",
            data={"text": "", "language": None, "segments": [], "words": []},
            diagnostics=["Análise premium desativada; transcrição ignorada."],
        )
        log("stems", "skipped", stems_result.diagnostics[0])
        log("transcription", "skipped", transcript_result.diagnostics[0])

    lyric_verification_options = lyric_verification_options or {}
    log("lyrics_validation", "running", "Verificando se a letra transcrita existe online...")
    lyric_validation_result = verify_transcript_exists(
        (transcript_result.data or {}).get("text", ""),
        title_hint=str(lyric_verification_options.get("title_hint") or ""),
        artist_hint=str(lyric_verification_options.get("artist_hint") or ""),
        source_name=source_title,
        duration_seconds=((payload or {}).get("metadata") or {}).get("duration_seconds"),
        genius_token=str(lyric_verification_options.get("genius_token") or ""),
        genius_client_id=str(lyric_verification_options.get("genius_client_id") or ""),
        genius_client_secret=str(lyric_verification_options.get("genius_client_secret") or ""),
    )
    log(
        "lyrics_validation",
        lyric_validation_result.mode or lyric_validation_result.status,
        lyric_validation_result.diagnostics[0] if lyric_validation_result.diagnostics else "Validação de letra concluída.",
    )

    matcher_result = find_mashup_candidates(payload)
    if matcher_sources.strip():
        matcher_result.metadata["source_notes"] = matcher_sources.strip()
        matcher_result.diagnostics.append("Fontes de pesquisa fornecidas pelo usuário foram anexadas ao matcher.")
    log("matcher", matcher_result.status, matcher_result.diagnostics[0] if matcher_result.diagnostics else "Matcher concluído.")

    pipeline_warnings: list[str] = []

    if run_agents:
        if not skills:
            agents_result = ResultEnvelope(
                status="failure",
                mode="disabled",
                data={},
                error="Skills de agentes não foram carregadas.",
                diagnostics=["Forneça skills válidas para executar a matriz de agentes."],
            )
            log("agents", "failure", "Skills de agentes não foram carregadas.")
            pipeline_warnings.append("As análises por IA foram puladas porque as skills não foram carregadas.")
        else:
            log("agents", "running", "Executando matriz de agentes e auditoria...")

            def agent_progress(step: int, message: str) -> None:
                log("agents", "running", f"{step}. {message}")

            try:
                agents_result = run_agent_pipeline(
                    {
                        "dsp_payload": payload,
                        "transcript_result": transcript_result.to_dict(),
                        "lyric_validation_result": lyric_validation_result.to_dict(),
                        "matcher_result": matcher_result.to_dict(),
                        "stems_result": stems_result.to_dict(),
                    },
                    skills,
                    progress_callback=agent_progress,
                    llm_options=agent_options,
                )
            except Exception as exc:
                agents_result = ResultEnvelope(
                    status="failure",
                    mode="failed",
                    data={},
                    error=f"Falha na matriz de agentes: {exc}",
                    diagnostics=[str(exc)],
                )
                log("agents", "failure", f"Falha na matriz de agentes: {exc}")
                pipeline_warnings.append(
                    "A matriz de agentes falhou, mas a análise local foi preservada. "
                    "Você pode trocar o modelo ou provider e tentar novamente sem recalcular tudo."
                )
            else:
                final_message = agents_result.error or (agents_result.diagnostics[0] if agents_result.diagnostics else "Agentes finalizados.")
                log("agents", agents_result.status, final_message)
                if agents_result.status != "success":
                    pipeline_warnings.append(
                        "A matriz de agentes não concluiu totalmente, mas o restante da análise ficou disponível."
                    )
    else:
        agents_result = ResultEnvelope(
            status="success",
            mode="skipped",
            data={},
            diagnostics=["Execução dos agentes desativada pelo usuário."],
        )
        log("agents", "skipped", agents_result.diagnostics[0])

    report = {
        "analysis_context": {
            "run_agents": run_agents,
            "enable_premium": enable_premium,
            "n_sections": n_sections,
            "matcher_sources": matcher_sources.strip(),
            "llm_provider": (agent_options or {}).get("provider"),
            "llm_model": (agent_options or {}).get("model"),
        },
        "source": source_result.to_dict(),
        "dsp": dsp_result.to_dict(),
        "loudness": loudness_result.to_dict(),
        "stems": stems_result.to_dict(),
        "transcript": transcript_result.to_dict(),
        "lyric_validation": lyric_validation_result.to_dict(),
        "matcher": matcher_result.to_dict(),
        "agents": agents_result.to_dict(),
        "stage_log": stage_log,
        "performance": _build_performance_report(stage_metrics, pipeline_started_at),
        "warnings": pipeline_warnings,
    }
    report["specialist_report"] = generate_specialist_report(report)
    report["text_report"] = generate_text_report(report)

    return PipelineResult(
        status="success",
        mode="completed_with_warnings" if pipeline_warnings else "completed",
        data=report,
        diagnostics=pipeline_warnings or ["Pipeline v2 concluído."],
        metadata={
            "stage_log": stage_log,
            "performance": report["performance"],
            "report_preview": json.dumps(report, ensure_ascii=False)[:500],
        },
    )
