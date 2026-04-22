"""Shared fixtures & helpers for artifact integration tests.

All integration tests bypass SurrealDB by mocking ``provision_langchain_model``
to return a LangChain model built directly from env-var provider keys. This
lets them make real LLM calls without requiring a live DB.
"""
from __future__ import annotations

import os

import pytest

# Providers we accept as valid (plan allowlist + LangChain provider variants)
VALID_PROVIDERS = {
    "anthropic",
    "openai",
    "openrouter",
    "google",
    "gemini",
    "xai",
    "groq",
    "mistral",
    "anthropic-chat",
    "openai-chat",
}


def has_provider_key() -> bool:
    """Return True if at least one LLM provider key is configured."""
    return any(
        os.environ.get(k)
        for k in (
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "OPENROUTER_API_KEY",
            "GOOGLE_API_KEY",
            "XAI_API_KEY",
        )
    )


def _bump_max_tokens(lc_model, max_tokens: int = 8192):
    """Esperanto defaults max_tokens=850 on Anthropic; bump so structured
    output for flashcards / larger schemas isn't truncated."""
    for attr in ("max_tokens", "max_completion_tokens"):
        if getattr(lc_model, attr, None) is not None:
            try:
                setattr(lc_model, attr, max_tokens)
            except Exception:
                pass
    return lc_model


def best_langchain_model():
    """Return the best available real LangChain model from env keys.

    Priority: Anthropic (cheap + good structured output) > OpenAI > OpenRouter.
    Bypasses SurrealDB entirely — used only by integration tests.
    """
    from esperanto import AIFactory

    if os.environ.get("ANTHROPIC_API_KEY"):
        m = AIFactory.create_language(
            model_name="claude-haiku-4-5-20251001", provider="anthropic"
        )
        return _bump_max_tokens(m.to_langchain())
    if os.environ.get("OPENAI_API_KEY"):
        m = AIFactory.create_language(model_name="gpt-4o-mini", provider="openai")
        return _bump_max_tokens(m.to_langchain())
    if os.environ.get("OPENROUTER_API_KEY"):
        m = AIFactory.create_language(
            model_name="openai/gpt-4o-mini", provider="openrouter"
        )
        return _bump_max_tokens(m.to_langchain())
    raise RuntimeError(
        "No provider key available to build a real LLM for integration test"
    )


def langchain_model_for_provider(env_var: str, model_id: str):
    """Build a LangChain model for a specific provider slot in the matrix.

    ``model_id`` looks like ``anthropic/claude-sonnet-4-6`` or
    ``openrouter/google/gemini-2.5-pro``. Returns a LangChain BaseChatModel
    so the test can skip the DB lookup that ``model_manager`` would do.
    """
    if not os.environ.get(env_var):
        pytest.skip(f"{env_var} not set — skipping {model_id}")

    from esperanto import AIFactory

    provider, _, name = model_id.partition("/")
    if provider == "anthropic":
        m = AIFactory.create_language(model_name=name, provider="anthropic")
    elif provider == "openai":
        m = AIFactory.create_language(model_name=name, provider="openai")
    elif provider == "openrouter":
        # For OpenRouter the "model_name" is the full `<upstream>/<name>` path.
        m = AIFactory.create_language(model_name=name, provider="openrouter")
    else:
        pytest.skip(f"unsupported provider for matrix: {provider}")
    return _bump_max_tokens(m.to_langchain())
