"""LLM layer for artifact generation.

Design:

- ``ArtifactLLM`` is LLM-primary. It calls ``provision_langchain_model``
  and uses LangChain's ``.with_structured_output(schema)`` to get strictly-
  typed Pydantic results. There is no "env flag" fallback — if a provider
  is configured, it is used, period.

- For offline / test / CI runs, callers inject an ``ArtifactLLM`` built on
  top of a :class:`StructuredMockChat` (or any callable implementing
  ``astructured(schema, messages) -> BaseModel``) via the ``chat`` kwarg
  or the ``DEFAULT_ARTIFACT_LLM`` contextvar. The mock implements the
  **same structured-output protocol** as the real LLM, so production
  code and test code run identical logic.

- A low-resolution heuristic emergency fallback survives only as a last
  line of defence when the structured-output call fails *and* the caller
  has not provided a mock. It's gated behind
  ``ARTIFACT_ALLOW_HEURISTIC_FALLBACK`` because shipping heuristics as
  "offline mode" is not acceptable product behaviour.
"""
from __future__ import annotations

import asyncio
import json
import os
from contextvars import ContextVar
from typing import Any, Callable, Dict, List, Optional, Protocol, Type, TypeVar, Union

from loguru import logger
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class StructuredChat(Protocol):
    """Minimal interface every LLM backend must implement.

    ``astructured`` must return an instance of ``schema`` (a Pydantic model)
    populated from the ``messages`` conversation. The ``system_prompt`` is
    the artifact-specific instruction block; ``user_prompt`` is the
    marshalled source content.
    """

    async def astructured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: Type[T],
        temperature: float = 0.1,
    ) -> T: ...

    async def atext(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
    ) -> str: ...


DEFAULT_ARTIFACT_LLM: ContextVar[Optional["ArtifactLLM"]] = ContextVar(
    "DEFAULT_ARTIFACT_LLM", default=None
)


class ArtifactLLMError(RuntimeError):
    """Raised when no LLM backend is available and no mock was injected."""


class ArtifactLLM:
    """Artifact-generation LLM facade.

    ``chat`` is any implementation of :class:`StructuredChat`. When
    omitted, the facade lazily builds a :class:`LangChainChat` against
    ``provision_langchain_model`` the first time it is used.
    """

    def __init__(
        self,
        chat: Optional[StructuredChat] = None,
        *,
        model_id: Optional[str] = None,
        default_type: str = "transformation",
        max_tokens: int = 4096,
    ) -> None:
        self._chat = chat
        self._model_id = model_id
        self._default_type = default_type
        self._max_tokens = max_tokens

    # ------------------------------------------------------------------
    # Factory / resolution
    # ------------------------------------------------------------------
    @classmethod
    def current(cls) -> "ArtifactLLM":
        """Return the context-var LLM if set, else build a default facade."""
        current = DEFAULT_ARTIFACT_LLM.get()
        if current is not None:
            return current
        return cls()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: Type[T],
        temperature: float = 0.1,
    ) -> T:
        chat = await self._resolve_chat()
        logger.debug(
            f"ArtifactLLM.structured schema={schema.__name__} "
            f"system_chars={len(system_prompt)} user_chars={len(user_prompt)}"
        )
        try:
            result = await chat.astructured(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                schema=schema,
                temperature=temperature,
            )
        except Exception as exc:
            if _heuristic_emergency_allowed():
                from open_notebook.artifacts.heuristic import heuristic_json

                logger.error(
                    f"ArtifactLLM: structured call failed ({exc!r}); "
                    "ARTIFACT_ALLOW_HEURISTIC_FALLBACK=1 — using emergency heuristic"
                )
                data = heuristic_json(
                    f"{system_prompt}\n\n# INPUT\n\n{user_prompt}",
                    artifact_type=schema.__name__.lower(),
                )
                return schema.model_validate(_coerce_to_schema(schema, data))
            raise ArtifactLLMError(str(exc)) from exc
        if not isinstance(result, schema):
            result = schema.model_validate(
                result.model_dump() if isinstance(result, BaseModel) else result
            )
        return result

    async def text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
    ) -> str:
        chat = await self._resolve_chat()
        return await chat.atext(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    async def _resolve_chat(self) -> StructuredChat:
        if self._chat is not None:
            return self._chat
        if not _has_provider_configured():
            raise ArtifactLLMError(
                "No LLM backend is configured and no mock was injected. "
                "Configure an AI provider (e.g. OPENAI_API_KEY) or inject "
                "an ArtifactLLM via DEFAULT_ARTIFACT_LLM / the `llm=` kwarg."
            )
        self._chat = LangChainChat(
            model_id=self._model_id,
            default_type=self._default_type,
            max_tokens=self._max_tokens,
        )
        return self._chat


# ----------------------------------------------------------------------
# Real backend: LangChain via provision_langchain_model
# ----------------------------------------------------------------------

class LangChainChat:
    """Backend that wraps a LangChain chat model with structured output.

    Resolution order for the underlying chat model:

    1. ``provision_langchain_model`` (the standard Open Notebook path,
       requires SurrealDB). Used when available.
    2. Direct LangChain instantiation keyed off of which provider env
       var is set (``OPENAI_API_KEY``, ``ANTHROPIC_API_KEY``, ...). This
       makes the artifact suite runnable from a plain Python script with
       nothing but a single API key in the environment.
    """

    _PROVIDER_MODELS = [
        ("OPENAI_API_KEY", "openai", "gpt-4o-mini"),
        ("ANTHROPIC_API_KEY", "anthropic", "claude-3-5-haiku-latest"),
        ("GROQ_API_KEY", "groq", "llama-3.1-70b-versatile"),
        ("GEMINI_API_KEY", "google_genai", "gemini-2.0-flash"),
        ("GOOGLE_API_KEY", "google_genai", "gemini-2.0-flash"),
        ("MISTRAL_API_KEY", "mistralai", "mistral-small-latest"),
        ("DEEPSEEK_API_KEY", "deepseek", "deepseek-chat"),
        ("XAI_API_KEY", "xai", "grok-2-latest"),
        ("OPENROUTER_API_KEY", "openai", "openai/gpt-4o-mini"),
    ]

    def __init__(
        self,
        *,
        model_id: Optional[str],
        default_type: str,
        max_tokens: int,
    ) -> None:
        self._model_id = model_id
        self._default_type = default_type
        self._max_tokens = max_tokens
        self._cached = None

    async def _chain(self):
        if self._cached is not None:
            return self._cached
        # Path 1: repo's provisioning layer (preferred).
        try:
            from open_notebook.ai.provision import provision_langchain_model
            chain = await provision_langchain_model(
                "artifact",
                self._model_id,
                self._default_type,
                max_tokens=self._max_tokens,
            )
            self._cached = chain
            return chain
        except Exception as exc:
            logger.info(
                f"provision_langchain_model unavailable ({exc.__class__.__name__}); "
                "falling back to direct LangChain instantiation from env vars"
            )

        # Path 2: direct instantiation via init_chat_model.
        try:
            from langchain.chat_models import init_chat_model
        except Exception as exc:
            raise RuntimeError(
                f"Cannot build LangChain chat model: {exc}"
            ) from exc

        for env_key, provider, model_name in self._PROVIDER_MODELS:
            if os.environ.get(env_key):
                logger.info(
                    f"ArtifactLLM direct backend: provider={provider} "
                    f"model={model_name}"
                )
                kwargs: Dict[str, Any] = {
                    "model_provider": provider,
                    "temperature": 0.1,
                }
                if provider == "openai" and env_key == "OPENROUTER_API_KEY":
                    kwargs["openai_api_base"] = "https://openrouter.ai/api/v1"
                    kwargs["openai_api_key"] = os.environ["OPENROUTER_API_KEY"]
                chain = init_chat_model(model_name, **kwargs)
                self._cached = chain
                return chain
        raise RuntimeError(
            "No LangChain chat provider could be instantiated. "
            "Ensure at least one of OPENAI_API_KEY, ANTHROPIC_API_KEY, "
            "GROQ_API_KEY, GEMINI_API_KEY, MISTRAL_API_KEY, DEEPSEEK_API_KEY, "
            "or XAI_API_KEY is set."
        )

    async def astructured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: Type[T],
        temperature: float = 0.1,
    ) -> T:
        from langchain_core.messages import HumanMessage, SystemMessage

        chain = await self._chain()
        try:
            structured = chain.with_structured_output(schema)
        except NotImplementedError:
            structured = chain.with_structured_output(schema, method="json_mode")
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        result = await structured.ainvoke(messages)
        if isinstance(result, dict):
            result = schema.model_validate(result)
        return result  # type: ignore[return-value]

    async def atext(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
    ) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage

        chain = await self._chain()
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        result = await chain.ainvoke(messages)
        content = getattr(result, "content", result)
        if isinstance(content, list):
            return "\n".join(
                b.get("text", "") if isinstance(b, dict) else str(b) for b in content
            )
        return str(content)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _has_provider_configured() -> bool:
    keys = (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GROQ_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "MISTRAL_API_KEY",
        "DEEPSEEK_API_KEY",
        "XAI_API_KEY",
        "OPENROUTER_API_KEY",
        "OLLAMA_API_BASE",
    )
    return any(os.environ.get(k) for k in keys)


def _heuristic_emergency_allowed() -> bool:
    return os.environ.get("ARTIFACT_ALLOW_HEURISTIC_FALLBACK", "0") in {
        "1", "true", "yes", "on"
    }


def _coerce_to_schema(schema: Type[BaseModel], data: Any) -> Any:
    """Best-effort coercion for emergency heuristic output into ``schema``."""
    try:
        schema.model_validate(data)
        return data
    except Exception:
        fields = getattr(schema, "model_fields", {})
        return {k: v for k, v in (data or {}).items() if k in fields}


def use_artifact_llm(llm: ArtifactLLM):
    """Context manager: set a default ``ArtifactLLM`` for the current ctx."""
    class _Scope:
        def __enter__(self_inner):
            self_inner._token = DEFAULT_ARTIFACT_LLM.set(llm)
            return llm

        def __exit__(self_inner, *_exc):
            DEFAULT_ARTIFACT_LLM.reset(self_inner._token)
    return _Scope()


# Back-compat re-export used by old helpers / tests.
def combine_prompts(instructions: str, context: str) -> str:
    return f"{instructions.strip()}\n\n# INPUT\n\n{context.strip()}"
