from __future__ import annotations

import json
from typing import Any

from services.llm_backends import call_llm_with_fallback, resolve_provider_candidates
from services.local_database import (
    list_copilot_messages,
    load_analysis_run,
    save_copilot_message,
    search_analysis_runs,
)


COPILOT_ACTIONS: dict[str, str] = {
    "current_analysis": "Responder sobre a análise atual",
    "history_search": "Consultar histórico local",
    "compare_runs": "Comparar análises salvas",
    "general_guidance": "Orientação musical geral",
}

SYSTEM_PROMPT = """
Você é o Copiloto Musical do AudioAgent, um assistente técnico para produtores, músicos e analistas.

Regras obrigatórias:
1. Diferencie claramente fatos medidos, metadados registrados, resultados validados, interpretações e hipóteses.
2. Nunca invente BPM, tonalidade, letra, instrumentos, artistas, datas, fontes ou resultados de pesquisa.
3. Use somente o contexto fornecido pela aplicação. Se faltar dado, diga exatamente o que falta.
4. Não afirme que pesquisou na internet. Este modo do Copiloto consulta apenas a análise aberta e a base local.
5. Não reproduza letras protegidas integralmente. Prefira paráfrase, análise temática e pequenos trechos quando necessários.
6. Explique termos técnicos em linguagem acessível e ofereça próximos passos práticos.
7. Quando comparar músicas, separe semelhanças objetivas de recomendações criativas.
8. Responda em português brasileiro, com estrutura curta e útil.
""".strip()


def _trim(value: Any, *, depth: int = 0, max_items: int = 12) -> Any:
    if depth >= 5:
        return "[conteúdo resumido]"
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).startswith("_"):
                continue
            cleaned[str(key)] = _trim(item, depth=depth + 1, max_items=max_items)
        return cleaned
    if isinstance(value, list):
        items = [_trim(item, depth=depth + 1, max_items=max_items) for item in value[:max_items]]
        if len(value) > max_items:
            items.append(f"[mais {len(value) - max_items} itens omitidos]")
        return items
    if isinstance(value, str) and len(value) > 5000:
        return value[:5000] + "\n[texto truncado pelo Copiloto]"
    if hasattr(value, "item") and callable(value.item):
        try:
            return value.item()
        except Exception:
            pass
    return value


def _current_analysis_context(pipeline_state: dict[str, Any] | None) -> dict[str, Any]:
    pipeline = ((pipeline_state or {}).get("data") or {}) if isinstance(pipeline_state, dict) else {}
    if not pipeline:
        return {"available": False, "message": "Nenhuma análise está aberta nesta sessão."}
    return {
        "available": True,
        "source": _trim(pipeline.get("source", {})),
        "dsp": _trim(pipeline.get("dsp", {})),
        "loudness": _trim(pipeline.get("loudness", {})),
        "stems": _trim(pipeline.get("stems", {})),
        "transcript": _trim(pipeline.get("transcript", {})),
        "lyric_validation": _trim(pipeline.get("lyric_validation", {})),
        "matcher": _trim(pipeline.get("matcher", {})),
        "agents": _trim(pipeline.get("agents", {})),
        "specialist_report": _trim(pipeline.get("specialist_report", {})),
        "performance": _trim(pipeline.get("performance", {})),
    }


def _history_context(query: str, selected_run_ids: list[str]) -> dict[str, Any]:
    summaries = search_analysis_runs(query=query, limit=12)
    selected_runs = []
    for run_id in selected_run_ids[:3]:
        loaded = load_analysis_run(run_id)
        if loaded:
            selected_runs.append(
                {
                    "entry": _trim(loaded.get("entry", {})),
                    "payload": _trim(loaded.get("payload", {}), max_items=8),
                }
            )
    return {
        "query": query,
        "matching_runs": _trim(summaries),
        "selected_runs": selected_runs,
    }


def _conversation_context(session_id: str) -> list[dict[str, str]]:
    messages = list_copilot_messages(session_id, limit=8)
    return [
        {
            "role": str(message.get("role", "")),
            "content": str(message.get("content", ""))[:1800],
        }
        for message in messages
    ]


def ask_copilot(
    *,
    session_id: str,
    question: str,
    action: str,
    pipeline_state: dict[str, Any] | None,
    llm_options: dict[str, Any],
    history_query: str = "",
    selected_run_ids: list[str] | None = None,
) -> dict[str, Any]:
    question = (question or "").strip()
    if not question:
        raise ValueError("Escreva uma pergunta para o Copiloto Musical.")
    if action not in COPILOT_ACTIONS:
        raise ValueError(f"Ação do Copiloto não suportada: {action}")

    selected_run_ids = selected_run_ids or []
    candidates = resolve_provider_candidates(llm_options)
    if not candidates:
        raise RuntimeError(
            "Nenhuma LLM está configurada. Abra `Configuração de LLM` na sidebar e informe ao menos uma API key válida."
        )

    local_context: dict[str, Any] = {
        "action": action,
        "action_label": COPILOT_ACTIONS[action],
        "question": question,
        "conversation": _conversation_context(session_id),
    }
    if action in {"current_analysis", "general_guidance"}:
        local_context["current_analysis"] = _current_analysis_context(pipeline_state)
    if action in {"history_search", "compare_runs"}:
        local_context["local_history"] = _history_context(history_query, selected_run_ids)

    save_copilot_message(
        session_id=session_id,
        role="user",
        content=question,
        action=action,
        metadata={"history_query": history_query, "selected_run_ids": selected_run_ids},
    )

    response = call_llm_with_fallback(
        candidates=candidates,
        system_prompt=SYSTEM_PROMPT,
        user_message=(
            "Responda à pergunta usando exclusivamente o dossiê local abaixo. "
            "Se a pergunta exigir pesquisa web, explique que essa integração ainda não está ativa "
            "e sugira quais fontes verificáveis consultar.\n\n"
            + json.dumps(local_context, ensure_ascii=False, indent=2, default=str)
        ),
        max_tokens=1800,
    )
    save_copilot_message(
        session_id=session_id,
        role="assistant",
        content=response["text"],
        action=action,
        provider=response["provider"],
        model=response["model"],
        metadata={
            "fallback_used": response["fallback_used"],
            "attempts": response["attempts"],
        },
    )
    return response

