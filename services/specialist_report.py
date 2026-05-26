from __future__ import annotations

from typing import Any


EVIDENCE_LABELS = {
    "medido_no_audio": "Medido no áudio",
    "detectado_por_algoritmo": "Detectado por algoritmo",
    "detectado_por_modelo": "Detectado por modelo",
    "validado_online": "Validado online",
    "interpretacao_ia": "Interpretação IA",
    "hipotese_producao": "Hipótese de produção",
    "nao_disponivel": "Não disponível",
}


def _get(container: dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = container
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else current


def _fmt_time(seconds: float | int | None) -> str:
    if seconds is None:
        return "n/d"
    seconds = max(0, int(float(seconds)))
    return f"{seconds // 60}:{seconds % 60:02d}"


def _claim(
    text: str,
    evidence_type: str,
    confidence: str,
    evidence: str,
    risk: str = "",
) -> dict[str, str]:
    return {
        "claim": text,
        "evidence_type": evidence_type,
        "evidence_label": EVIDENCE_LABELS.get(evidence_type, evidence_type),
        "confidence": confidence,
        "evidence": evidence,
        "risk": risk,
    }


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _energy_label(value: Any) -> str:
    energy = _safe_float(value)
    if energy is None:
        return "energia não medida"
    if energy >= 0.72:
        return "alta energia"
    if energy >= 0.42:
        return "energia média"
    return "baixa energia"


def _section_function(index: int, section: dict[str, Any], peak_index: int | None, low_index: int | None) -> str:
    label = str(section.get("section_label") or f"Seção {index + 1}")
    if index == peak_index:
        return "Provável ponto de maior impacto ou clímax energético da faixa."
    if index == low_index:
        return "Provável respiro estrutural, breakdown ou trecho de menor densidade."
    if index == 0:
        return "Entrada da faixa; pode funcionar como introdução ou ponto de mixagem."
    if "Build" in label:
        return "Trecho nomeado como build pelo template DSP; use como hipótese até validação auditiva."
    if "Drop" in label:
        return "Trecho nomeado como drop/outro pelo template DSP; confirme pelo áudio antes de tratar como fato."
    return "Bloco estrutural detectado por divisão temporal e energia relativa."


def _performance_hint(section: dict[str, Any]) -> str:
    dominant = section.get("dominant_stem")
    energy = _safe_float(section.get("relative_energy_score")) or 0.0
    if dominant == "vocals":
        return "Se houver voz neste trecho, priorize clareza de articulação e espaço nos médios."
    if dominant == "drums" and energy >= 0.55:
        return "Trecho propício para leitura de groove, impacto de kick/percussão e transição de energia."
    if dominant == "bass":
        return "Atenção ao low-end: bom ponto para avaliar peso, subgrave e compatibilidade de mashup."
    if energy < 0.35:
        return "Trecho mais aberto para vocal, atmosfera, pausa dramática ou preparação."
    return "Avalie densidade, abertura estéreo e função de sustentação no arranjo."


def _production_hint(section: dict[str, Any]) -> str:
    dominant = section.get("dominant_stem")
    energy = _safe_float(section.get("relative_energy_score")) or 0.0
    if dominant == "drums":
        return "Hipótese: foco em transientes/percussão; verificar kick, sidechain e hats no áudio."
    if dominant == "vocals":
        return "Hipótese: pocket vocal nos médios; verificar reverbs, delays e inteligibilidade."
    if energy >= 0.72:
        return "Hipótese: maior densidade de camadas, abertura espectral ou clímax de mix."
    if energy <= 0.35:
        return "Hipótese: filtragem, redução de elementos ou trecho atmosférico."
    return "Hipótese: seção de transição ou sustentação; confirmar por escuta."


def _build_timeline(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not sections:
        return []
    energies = [_safe_float(item.get("relative_energy_score")) or 0.0 for item in sections]
    peak_index = max(range(len(energies)), key=lambda idx: energies[idx]) if energies else None
    low_index = min(range(len(energies)), key=lambda idx: energies[idx]) if energies else None
    timeline = []
    for index, section in enumerate(sections):
        energy = _safe_float(section.get("relative_energy_score"))
        timeline.append(
            {
                "timestamp": f"{section.get('timestamp_start', 'n/d')} - {section.get('timestamp_end', 'n/d')}",
                "detected_label": section.get("section_label") or f"Seção {index + 1}",
                "energy": energy,
                "energy_label": _energy_label(energy),
                "dominant_stem": section.get("dominant_stem", "n/d"),
                "function": _section_function(index, section, peak_index, low_index),
                "performance_hint": _performance_hint(section),
                "production_hint": _production_hint(section),
                "evidence_type": "detectado_por_algoritmo",
                "confidence": "medium",
                "evidence": "Divisão temporal, RMS relativo e estimativa HPSS do DSP local.",
            }
        )
    return timeline


def _infer_rubric(metrics: dict[str, Any], loudness_data: dict[str, Any], source_title: str) -> dict[str, str]:
    bpm = _safe_float(metrics.get("bpm_measured"))
    title_lower = source_title.lower()
    if bpm and 128 <= bpm <= 155:
        return {
            "family": "EDM / Trance / Dancefloor",
            "confidence": "medium",
            "basis": f"BPM medido em {bpm:.1f}, faixa típica de música eletrônica de pista. Não prova gênero sozinho.",
        }
    if any(term in title_lower for term in ("orchestral", "cinematic", "epic", "trailer")):
        return {
            "family": "Cinematic / Orchestral",
            "confidence": "medium",
            "basis": "Termos encontrados no título/fonte. Precisa de validação por instrumentação real.",
        }
    lufs = _safe_float(loudness_data.get("integrated_lufs"))
    if lufs is not None and lufs <= -8.5:
        return {
            "family": "Master moderna de alta pressão",
            "confidence": "low",
            "basis": f"LUFS integrado em {lufs}; isso descreve loudness, não gênero.",
        }
    return {
        "family": "Rubrica geral",
        "confidence": "low",
        "basis": "Não há evidência suficiente para escolher uma rubrica especializada com segurança.",
    }


def _build_claims(
    source_data: dict[str, Any],
    dsp_data: dict[str, Any],
    loudness_data: dict[str, Any],
    transcript_result: dict[str, Any],
    lyric_validation_result: dict[str, Any],
    agents_result: dict[str, Any],
) -> list[dict[str, str]]:
    metrics = dsp_data.get("acoustic_metrics", {}) or {}
    meta = dsp_data.get("metadata", {}) or {}
    freq = metrics.get("frequency_distribution", {}) or {}
    transcript_data = transcript_result.get("data", {}) or {}
    lyric_data = lyric_validation_result.get("data", {}) or {}
    agent_data = agents_result.get("data", {}) or {}

    claims = [
        _claim(
            f"Duração analisada: {_fmt_time(meta.get('duration_seconds'))} ({meta.get('duration_seconds', 'n/d')} s).",
            "medido_no_audio",
            "high",
            "Duração calculada pelo carregamento local do arquivo de áudio.",
        ),
        _claim(
            f"BPM estimado: {metrics.get('bpm_measured', 'n/d')}.",
            "medido_no_audio",
            "medium",
            "Beat tracking via Librosa; pode variar em faixas com rubato, breaks longos ou intro sem bateria.",
            "Validar por escuta/metrônomo antes de usar como valor final de produção.",
        ),
        _claim(
            f"Tonalidade provável: {metrics.get('key_note', 'n/d')} {str(metrics.get('key_mode', '')).capitalize()} / Camelot {metrics.get('camelot_key', 'n/d')}.",
            "detectado_por_algoritmo",
            "medium",
            "Estimativa por chroma/key profile no DSP.",
            "Pode errar em modulações, samples, covers, músicas com centro tonal ambíguo ou mixagens densas.",
        ),
        _claim(
            f"Distribuição espectral: graves {freq.get('low_energy_db', 'n/d')} dB, médios {freq.get('mid_energy_db', 'n/d')} dB, agudos {freq.get('high_energy_db', 'n/d')} dB.",
            "medido_no_audio",
            "medium",
            "Energia por bandas calculada no espectro do áudio completo.",
        ),
    ]

    if loudness_data:
        if "integrated_lufs" in loudness_data:
            claims.append(
                _claim(
                    f"Loudness integrado: {loudness_data.get('integrated_lufs')} LUFS.",
                    "medido_no_audio",
                    "high" if loudness_data.get("method") == "pyloudnorm_integrated_lufs" else "medium",
                    f"Método: {loudness_data.get('method', 'n/d')}.",
                )
            )
        claims.append(
            _claim(
                f"Sample peak: {loudness_data.get('sample_peak_dbfs', 'n/d')} dBFS; crest factor: {loudness_data.get('crest_factor_db', 'n/d')} dB.",
                "medido_no_audio",
                "medium",
                "Medição no áudio decodificado localmente; não substitui medição True Peak dedicada.",
                "Em MP3 decodificado como float, picos acima de 0 dBFS podem aparecer e devem ser interpretados com cautela.",
            )
        )

    if transcript_data.get("text"):
        claims.append(
            _claim(
                "Há transcrição local de voz disponível para análise lírica/prosódica.",
                "detectado_por_modelo",
                "medium",
                f"Modo de transcrição: {transcript_result.get('mode', 'n/d')}; segmentos: {len(transcript_data.get('segments', []) or [])}.",
                "Música cantada pode gerar palavras incorretas; revisar antes de publicar/exportar letra integral.",
            )
        )
    else:
        claims.append(
            _claim(
                "Não há transcrição local de letra nesta rodada.",
                "nao_disponivel",
                "high",
                "WhisperX foi pulado, falhou ou não retornou texto utilizável.",
            )
        )

    if lyric_data.get("validated"):
        claims.append(
            _claim(
                "A faixa/letra teve validação online positiva.",
                "validado_online",
                "medium",
                "Validação por serviços configurados na aplicação.",
                "Validação online não autoriza reprodução integral de letras protegidas.",
            )
        )
    elif lyric_validation_result:
        claims.append(
            _claim(
                "Não houve validação online positiva da letra/faixa nesta rodada.",
                "nao_disponivel",
                "medium",
                "Resultado da etapa de verificação de letra.",
            )
        )

    for label, key in (
        ("DNA instrumental", "dna"),
        ("Blueprint estrutural", "blueprint"),
        ("DNA lírico", "lyrics_dna"),
        ("DAW/Mix", "daw_guidance"),
    ):
        if agent_data.get(key):
            claims.append(
                _claim(
                    f"{label} foi gerado por LLM e deve ser lido como interpretação assistida.",
                    "interpretacao_ia",
                    "medium",
                    "Saída textual da matriz de agentes baseada no pacote de dados do pipeline.",
                    "Pode conter hipóteses técnicas; validar afirmações específicas com áudio, stems ou metadados.",
                )
            )

    if source_data.get("source_url"):
        claims.append(
            _claim(
                "A análise partiu de um link informado pelo usuário.",
                "validado_online",
                "medium",
                "Proveniência registrada pela etapa de ingestão.",
                "Uso/download de conteúdo de plataformas deve respeitar direitos e autorização do usuário.",
            )
        )

    return claims


def _claim_counts(claims: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for claim in claims:
        label = claim.get("evidence_label") or claim.get("evidence_type") or "Outro"
        counts[label] = counts.get(label, 0) + 1
    return counts


def _markdown_list(title: str, items: list[str]) -> list[str]:
    lines = [title, "-" * 80]
    if items:
        lines.extend(f"- {item}" for item in items)
    else:
        lines.append("- Não disponível nesta rodada.")
    lines.append("")
    return lines


def build_specialist_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    identification = report.get("identification", {})
    measured = report.get("measured_data", {})
    rubric = report.get("rubric", {})
    timeline = report.get("structure_timeline", [])
    claims = report.get("claims", [])

    lines.append("Relatório Especialista v1")
    lines.append("=" * 80)
    lines.append("")
    lines.append("Identificação")
    lines.append("-" * 80)
    lines.append(f"Faixa: {identification.get('title', 'n/d')}")
    lines.append(f"Artista: {identification.get('artist', 'n/d')}")
    lines.append(f"Origem: {identification.get('source_type', 'n/d')}")
    lines.append(f"Duração: {identification.get('duration_label', 'n/d')}")
    lines.append("")

    lines.append("Dados Medidos")
    lines.append("-" * 80)
    for key, value in measured.items():
        lines.append(f"- {key}: {value}")
    lines.append("")

    lines.append("Rubrica Selecionada")
    lines.append("-" * 80)
    lines.append(f"- Família: {rubric.get('family', 'n/d')}")
    lines.append(f"- Confiança: {rubric.get('confidence', 'n/d')}")
    lines.append(f"- Base: {rubric.get('basis', 'n/d')}")
    lines.append("")

    lines.append("Estrutura por Tempo")
    lines.append("-" * 80)
    for item in timeline:
        lines.append(
            f"- {item.get('timestamp')} | {item.get('detected_label')} | "
            f"{item.get('energy_label')} | dominante: {item.get('dominant_stem')}"
        )
        lines.append(f"  Função: {item.get('function')}")
        lines.append(f"  Performance: {item.get('performance_hint')}")
        lines.append(f"  Produção: {item.get('production_hint')}")
    lines.append("")

    lines.extend(_markdown_list("DNA Musical", report.get("audio_dna", [])))
    lines.extend(_markdown_list("DNA Vocal e Lírico", report.get("vocal_lyrical_dna", [])))
    lines.extend(_markdown_list("DNA de Produção e Mix", report.get("production_dna", [])))
    lines.extend(_markdown_list("Veredito", report.get("verdict", [])))

    lines.append("Evidências e Incertezas")
    lines.append("-" * 80)
    for item in claims:
        lines.append(
            f"- [{item.get('evidence_label')}; confiança {item.get('confidence')}] "
            f"{item.get('claim')} Evidência: {item.get('evidence')}"
        )
        if item.get("risk"):
            lines.append(f"  Cautela: {item.get('risk')}")
    return "\n".join(lines).strip() + "\n"


def generate_specialist_report(report_payload: dict[str, Any]) -> dict[str, Any]:
    source_data = _get(report_payload, "source", "data", default={}) or {}
    dsp_data = _get(report_payload, "dsp", "data", default={}) or {}
    metrics = dsp_data.get("acoustic_metrics", {}) or {}
    meta = dsp_data.get("metadata", {}) or {}
    loudness_data = _get(report_payload, "loudness", "data", default={}) or {}
    transcript_result = report_payload.get("transcript", {}) or {}
    lyric_validation_result = report_payload.get("lyric_validation", {}) or {}
    agents_result = report_payload.get("agents", {}) or {}

    source_title = source_data.get("title") or source_data.get("source_name") or meta.get("source_name") or "Faixa analisada"
    duration = meta.get("duration_seconds")
    timeline = _build_timeline(dsp_data.get("timeline_sections", []) or [])
    rubric = _infer_rubric(metrics, loudness_data, str(source_title))
    claims = _build_claims(source_data, dsp_data, loudness_data, transcript_result, lyric_validation_result, agents_result)
    freq = metrics.get("frequency_distribution", {}) or {}
    transcript_data = transcript_result.get("data", {}) or {}
    lyric_data = lyric_validation_result.get("data", {}) or {}

    measured_data = {
        "BPM": metrics.get("bpm_measured", "n/d"),
        "Tonalidade provável": f"{metrics.get('key_note', 'n/d')} {str(metrics.get('key_mode', '')).capitalize()}",
        "Camelot": metrics.get("camelot_key", "n/d"),
        "Duração": f"{duration} s",
        "LUFS integrado": loudness_data.get("integrated_lufs", "n/d"),
        "Sample Peak": loudness_data.get("sample_peak_dbfs", "n/d"),
        "Range proxy": loudness_data.get("loudness_range_proxy_lu", "n/d"),
        "Correlação estéreo": loudness_data.get("stereo_correlation", "n/d"),
    }

    audio_dna = [
        f"Pulso central em {metrics.get('bpm_measured', 'n/d')} BPM, medido por beat tracking local.",
        f"Centro tonal provável em {metrics.get('key_note', 'n/d')} {str(metrics.get('key_mode', '')).capitalize()}, com Camelot {metrics.get('camelot_key', 'n/d')}.",
        f"Perfil espectral medido: graves {freq.get('low_energy_db', 'n/d')} dB, médios {freq.get('mid_energy_db', 'n/d')} dB e agudos {freq.get('high_energy_db', 'n/d')} dB.",
        f"Estrutura dividida em {len(timeline)} blocos para leitura de energia e função musical.",
    ]

    vocal_lyrical_dna = []
    if transcript_data.get("text"):
        vocal_lyrical_dna.append(
            "Transcrição local disponível; use a aba Letra & Prosódia para revisar texto e timestamps antes de qualquer uso público."
        )
    else:
        vocal_lyrical_dna.append(
            "Sem transcrição local nesta rodada; qualquer análise lírica deve vir de metadados/fonte validada ou de paráfrase, não de letra inventada."
        )
    if lyric_data.get("validated"):
        vocal_lyrical_dna.append("Validação online encontrou correspondência; ainda assim, reprodução integral de letra depende de licença/autorização.")
    else:
        vocal_lyrical_dna.append("Validação online não confirmou letra/faixa de forma positiva nesta rodada.")

    production_dna = []
    if loudness_data:
        production_dna.append(
            f"Loudness/dinâmica: LUFS {loudness_data.get('integrated_lufs', 'n/d')}, crest factor {loudness_data.get('crest_factor_db', 'n/d')} dB e sample peak {loudness_data.get('sample_peak_dbfs', 'n/d')} dBFS."
        )
    if rubric["family"] != "Rubrica geral":
        production_dna.append(f"Rubrica de leitura sugerida: {rubric['family']} ({rubric['basis']})")
    production_dna.append(
        "Termos como sidechain, shimmer, supersaw, close miking ou braaam só devem aparecer como hipótese se não houver medição/modelo específico sustentando a afirmação."
    )

    verdict = [
        "A análise local já sustenta decisões objetivas sobre andamento, tonalidade provável, loudness, energia e estrutura aproximada.",
        "A camada interpretativa deve ser usada como guia criativo, não como prova técnica isolada.",
        "Para elevar a precisão, os próximos reforços são identificação musical por fingerprint/metadados, rubricas por gênero e análise de instrumentação/stems mais rica.",
    ]

    report = {
        "version": "specialist_report_v1",
        "identification": {
            "title": source_title,
            "artist": source_data.get("artist") or "Não identificado",
            "source_type": source_data.get("source_type") or "n/d",
            "source_url": source_data.get("source_url", ""),
            "audio_path": source_data.get("audio_path") or meta.get("source_path", ""),
            "duration_seconds": duration,
            "duration_label": _fmt_time(duration),
        },
        "rubric": rubric,
        "measured_data": measured_data,
        "structure_timeline": timeline,
        "audio_dna": audio_dna,
        "vocal_lyrical_dna": vocal_lyrical_dna,
        "production_dna": production_dna,
        "verdict": verdict,
        "claims": claims,
        "evidence_summary": _claim_counts(claims),
    }
    report["markdown"] = build_specialist_markdown(report)
    return report
