from __future__ import annotations

from typing import Any

from services.config import (
    LLM_PROVIDER_SPECS,
    llm_default_model,
    resolve_llm_api_key,
)


class LLMProviderError(RuntimeError):
    """Raised when a configured LLM provider cannot fulfill a request."""


def _stringify(value: Any) -> str:
    return "" if value is None else str(value)


def normalize_provider(provider: str | None) -> str:
    normalized = (provider or "anthropic").strip().lower()
    if normalized not in LLM_PROVIDER_SPECS:
        raise LLMProviderError(f"Provider de LLM não suportado: {provider}")
    return normalized


def resolve_provider_config(options: dict[str, Any] | None) -> dict[str, str]:
    candidates = resolve_provider_candidates(options)
    if candidates:
        return candidates[0]

    provider = normalize_provider(str((options or {}).get("provider") or "anthropic"))
    env_var = str(LLM_PROVIDER_SPECS[provider]["env_var"])
    raise LLMProviderError(
        f"API key ausente para {LLM_PROVIDER_SPECS[provider]['label']}. "
        f"Defina {env_var} no ambiente ou informe a chave na sidebar."
    )


def resolve_provider_candidates(options: dict[str, Any] | None) -> list[dict[str, str]]:
    options = options or {}
    primary_provider = normalize_provider(str(options.get("provider") or "anthropic"))
    configured_api_keys = options.get("configured_api_keys", {})
    configured_models = options.get("configured_models", {})
    fallback_enabled = bool(options.get("fallback_enabled", True))
    fallback_order = options.get("fallback_order", [])

    if not isinstance(configured_api_keys, dict):
        configured_api_keys = {}
    if not isinstance(configured_models, dict):
        configured_models = {}
    if not isinstance(fallback_order, list):
        fallback_order = []

    provider_order = [primary_provider]
    for candidate in fallback_order:
        normalized = normalize_provider(str(candidate))
        if normalized not in provider_order:
            provider_order.append(normalized)
    if fallback_enabled:
        for provider in LLM_PROVIDER_SPECS:
            if provider not in provider_order:
                provider_order.append(provider)

    candidates: list[dict[str, str]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for provider in provider_order:
        explicit_api_key = (
            _stringify(options.get("api_key"))
            if provider == primary_provider
            else _stringify(configured_api_keys.get(provider))
        )
        explicit_model = (
            _stringify(options.get("model"))
            if provider == primary_provider
            else _stringify(configured_models.get(provider))
        )
        api_key = resolve_llm_api_key(provider, explicit_api_key)
        if not api_key:
            continue
        models_to_try: list[str] = []
        selected_model = explicit_model or llm_default_model(provider)
        if selected_model:
            models_to_try.append(selected_model)
        for fallback_model in LLM_PROVIDER_SPECS[provider].get("fallback_models", []):
            fallback_name = _stringify(fallback_model)
            if fallback_name and fallback_name not in models_to_try:
                models_to_try.append(fallback_name)

        for model in models_to_try:
            key = (provider, model)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            candidates.append(
                {
                    "provider": provider,
                    "model": model,
                    "api_key": api_key,
                }
            )
        if not fallback_enabled:
            break
    return candidates


def _friendly_failure_reason(provider: str, model: str, raw_error: str) -> str:
    text = raw_error.lower()
    label = str(LLM_PROVIDER_SPECS[provider]["label"])

    if "model_not_found" in text or "does not have access to model" in text or "not have access to model" in text:
        return f"{label} respondeu, mas esta conta/projeto não tem acesso ao modelo `{model}`."
    if "invalid x-api-key" in text or "incorrect api key" in text or "authentication_error" in text or "api key" in text and "invalid" in text:
        return f"A API key configurada para {label} parece inválida ou expirou."
    if "insufficient_quota" in text or "quota" in text or "billing" in text or "credit balance" in text:
        return f"{label} recusou a chamada por cota, saldo ou billing."
    if "rate limit" in text or "429" in text or "resource exhausted" in text:
        return f"{label} limitou temporariamente as requisições."
    if "timeout" in text or "timed out" in text:
        return f"{label} demorou demais para responder."
    return f"{label} falhou ao executar o modelo `{model}`."


def _build_fallback_error(attempts: list[dict[str, str]]) -> str:
    if not attempts:
        return (
            "Nenhuma LLM estava pronta para uso. Cadastre ao menos uma API key válida "
            "na seção Configuração de LLM."
        )

    details = " | ".join(
        f"{item['label']} ({item['model']}): {item['message']}"
        for item in attempts
        if item.get("status") == "failure"
    )
    return (
        "Nenhuma das LLMs configuradas conseguiu concluir a chamada. "
        f"Tentativas: {details}"
    )


def _extract_openai_text(response: Any) -> str:
    if getattr(response, "choices", None):
        choice = response.choices[0]
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                text = getattr(item, "text", None)
                if text:
                    parts.append(text)
            if parts:
                return "\n".join(parts)
    raise LLMProviderError("A resposta da OpenAI não trouxe conteúdo textual legível.")


def call_llm(
    *,
    provider: str,
    model: str,
    api_key: str,
    system_prompt: str,
    user_message: str,
    max_tokens: int = 2048,
) -> str:
    provider = normalize_provider(provider)

    try:
        if provider == "anthropic":
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            return response.content[0].text

        if provider == "openai":
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
            return _extract_openai_text(response)

        if provider == "gemini":
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model,
                contents=user_message,
                config=types.GenerateContentConfig(
                    systemInstruction=system_prompt,
                    maxOutputTokens=max_tokens,
                    temperature=0.4,
                ),
            )
            if getattr(response, "text", None):
                return response.text
            raise LLMProviderError("A resposta do Gemini não trouxe texto utilizável.")
    except LLMProviderError:
        raise
    except Exception as exc:
        label = str(LLM_PROVIDER_SPECS[provider]["label"])
        raise LLMProviderError(f"Falha ao chamar {label}: {exc}") from exc

    raise LLMProviderError(f"Provider de LLM não implementado: {provider}")


def call_llm_with_fallback(
    *,
    candidates: list[dict[str, str]],
    system_prompt: str,
    user_message: str,
    max_tokens: int = 2048,
) -> dict[str, Any]:
    if not candidates:
        raise LLMProviderError(
            "Nenhuma LLM configurada com API key disponível. "
            "Cadastre ao menos uma chave válida na seção Configuração de LLM."
        )

    attempts: list[dict[str, str]] = []
    primary = candidates[0]

    for candidate in candidates:
        provider = candidate["provider"]
        model = candidate["model"]
        label = str(LLM_PROVIDER_SPECS[provider]["label"])
        try:
            text = call_llm(
                provider=provider,
                model=model,
                api_key=candidate["api_key"],
                system_prompt=system_prompt,
                user_message=user_message,
                max_tokens=max_tokens,
            )
            attempts.append(
                {
                    "provider": provider,
                    "label": label,
                    "model": model,
                    "status": "success",
                    "message": "Chamada concluída com sucesso.",
                }
            )
            return {
                "text": text,
                "provider": provider,
                "model": model,
                "label": label,
                "fallback_used": provider != primary["provider"] or model != primary["model"] or len(attempts) > 1,
                "attempts": attempts,
            }
        except LLMProviderError as exc:
            attempts.append(
                {
                    "provider": provider,
                    "label": label,
                    "model": model,
                    "status": "failure",
                    "message": _friendly_failure_reason(provider, model, str(exc)),
                    "raw_error": str(exc),
                }
            )

    raise LLMProviderError(_build_fallback_error(attempts))
