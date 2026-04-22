"""LLM adapter for artifact generation.

Real-LLM-only. There is no heuristic fallback. If provisioning or generation
fails, the call raises ``ExternalServiceError`` and the caller (usually the
surreal-commands job with retry) handles it.

Features:
- Structured output via LangChain ``with_structured_output(PydanticModel)``,
  dispatched per-provider (OpenAI json_schema, Anthropic tool-use, Gemini
  response_schema, OpenRouter pass-through).
- Full provenance tracking: every call appends a ``LLMCallRecord`` to the
  active :class:`GenerationProvenance` so downstream code can prove real
  model usage and persist telemetry.
- Tenacity-driven retries with exponential backoff for transient errors.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from typing import Any, Awaitable, Callable, Dict, List, Optional, Type

from loguru import logger
from pydantic import BaseModel
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from open_notebook.exceptions import (
    ConfigurationError,
    ExternalServiceError,
    RateLimitError,
)

TextGenerator = Callable[[str], Awaitable[str]]


class LLMCallRecord(BaseModel):
    """A single LLM invocation's provenance data."""

    prompt_hash: str
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    latency_ms: Optional[int] = None
    attempt: int = 1
    provider: Optional[str] = None
    model: Optional[str] = None
    status: str = "ok"
    error_class: Optional[str] = None


class GenerationProvenance(BaseModel):
    """Full provenance for a single artifact generation run.

    Attached to every ``ArtifactResult``. Tests assert ``calls`` is non-empty
    to prove a real LLM was invoked — this is the third layer of the
    "no fake output" guard (see plan §§ Test Tiers).
    """

    run_id: str
    artifact_type: str
    model_id: Optional[str] = None
    default_type: str = "transformation"
    calls: List[LLMCallRecord] = []

    def add_call(self, record: LLMCallRecord) -> None:
        self.calls.append(record)


class ArtifactLLM:
    """Thin facade over ``provision_langchain_model`` with structured output.

    No heuristic fallback. If the provider is unreachable or returns garbage,
    we raise ``ExternalServiceError`` and let the job-queue retry wrapper
    handle it.
    """

    # Transient errors we retry. ConfigurationError never gets retried since
    # it indicates a setup bug, not a transient failure.
    RETRYABLE = (ExternalServiceError, RateLimitError, ConnectionError, TimeoutError)

    def __init__(
        self,
        text_generator: Optional[TextGenerator] = None,
        default_type: str = "transformation",
        model_id: Optional[str] = None,
        max_tokens: int = 16384,
        artifact_type: str = "unknown",
        provenance: Optional[GenerationProvenance] = None,
    ) -> None:
        self._text_generator = text_generator
        self._default_type = default_type
        self._model_id = model_id
        self._max_tokens = max_tokens
        self._artifact_type = artifact_type
        self.provenance = provenance or GenerationProvenance(
            run_id=str(uuid.uuid4()),
            artifact_type=artifact_type,
            model_id=model_id,
            default_type=default_type,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def generate_text(self, prompt: str) -> str:
        """Return free-form text from the LLM.

        Tests can inject ``text_generator`` to bypass the provider call; in
        that case we still record a provenance entry so no-call tests fail.
        """
        if self._text_generator is not None:
            return await self._invoke_injected(prompt)
        return await self._invoke_langchain_text(prompt)

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[BaseModel],
    ) -> BaseModel:
        """Return a validated Pydantic instance via provider-native structured output.

        Failure modes:
        - Provider/network errors → retried via tenacity, then raised as
          ``ExternalServiceError``.
        - Schema validation errors → raised as ``ExternalServiceError``
          (no heuristic rescue; the job retry handles it).
        """
        if self._text_generator is not None:
            raw = await self._invoke_injected(prompt)
            return _validate_schema(raw, schema)

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential_jitter(initial=1, max=20),
            retry=retry_if_exception_type(self.RETRYABLE),
            reraise=True,
        ):
            with attempt:
                return await self._invoke_langchain_structured(
                    prompt, schema, attempt.retry_state.attempt_number
                )
        # Unreachable because reraise=True; keep mypy happy.
        raise ExternalServiceError("structured output retries exhausted")

    async def generate_json(
        self,
        prompt: str,
        schema: Type[BaseModel],
    ) -> Dict[str, Any]:
        """Dict flavour of :meth:`generate_structured` for call-sites that
        want a plain mapping (most renderers prefer this)."""
        model = await self.generate_structured(prompt, schema)
        return model.model_dump()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    async def _invoke_injected(self, prompt: str) -> str:
        """Path used by tests: call the injected generator and record it."""
        start = time.perf_counter()
        record = LLMCallRecord(
            prompt_hash=_prompt_hash(prompt),
            provider="injected",
            model="test-generator",
        )
        try:
            out = await self._text_generator(prompt)  # type: ignore[misc]
            record.latency_ms = int((time.perf_counter() - start) * 1000)
            record.tokens_out = len(out.split())
            record.tokens_in = len(prompt.split())
            self.provenance.add_call(record)
            return out
        except Exception as exc:
            record.status = "error"
            record.error_class = type(exc).__name__
            record.latency_ms = int((time.perf_counter() - start) * 1000)
            self.provenance.add_call(record)
            raise

    async def _invoke_langchain_text(self, prompt: str) -> str:
        from langchain_core.messages import HumanMessage

        from open_notebook.ai.provision import provision_langchain_model

        start = time.perf_counter()
        record = LLMCallRecord(prompt_hash=_prompt_hash(prompt))
        try:
            chain = await provision_langchain_model(
                content=prompt,
                model_id=self._model_id,
                default_type=self._default_type,
                max_tokens=self._max_tokens,
            )
            record.provider = _provider_from_chain(chain)
            record.model = _model_name_from_chain(chain)
            result = await chain.ainvoke([HumanMessage(content=prompt)])
        except ConfigurationError:
            record.status = "config_error"
            self.provenance.add_call(record)
            raise
        except Exception as exc:
            record.status = "error"
            record.error_class = type(exc).__name__
            record.latency_ms = int((time.perf_counter() - start) * 1000)
            self.provenance.add_call(record)
            logger.warning(
                f"ArtifactLLM text generation failed "
                f"(artifact={self._artifact_type}, "
                f"provider={record.provider}): {exc}"
            )
            raise ExternalServiceError(
                f"LLM call failed for {self._artifact_type}: {exc}"
            ) from exc

        record.latency_ms = int((time.perf_counter() - start) * 1000)
        content = _extract_content(result)
        record.tokens_in, record.tokens_out = _extract_token_usage(result, prompt, content)
        self.provenance.add_call(record)
        _emit_llm_log(record, self._artifact_type)
        return content

    async def _invoke_langchain_structured(
        self,
        prompt: str,
        schema: Type[BaseModel],
        attempt_num: int,
    ) -> BaseModel:
        from langchain_core.messages import HumanMessage

        from open_notebook.ai.provision import provision_langchain_model

        start = time.perf_counter()
        record = LLMCallRecord(prompt_hash=_prompt_hash(prompt), attempt=attempt_num)
        try:
            chain = await provision_langchain_model(
                content=prompt,
                model_id=self._model_id,
                default_type=self._default_type,
                max_tokens=self._max_tokens,
            )
            record.provider = _provider_from_chain(chain)
            record.model = _model_name_from_chain(chain)

            structured = _bind_structured_output(chain, schema)
            result = await structured.ainvoke([HumanMessage(content=prompt)])
        except ConfigurationError:
            record.status = "config_error"
            self.provenance.add_call(record)
            raise
        except Exception as exc:
            record.status = "error"
            record.error_class = type(exc).__name__
            record.latency_ms = int((time.perf_counter() - start) * 1000)
            self.provenance.add_call(record)
            logger.warning(
                f"ArtifactLLM structured generation failed "
                f"(artifact={self._artifact_type}, attempt={attempt_num}, "
                f"provider={record.provider}): {exc}"
            )
            raise ExternalServiceError(
                f"LLM structured call failed for {self._artifact_type}: {exc}"
            ) from exc

        record.latency_ms = int((time.perf_counter() - start) * 1000)
        # Best-effort usage capture. Some providers attach usage on the raw
        # result, others strip it when going through with_structured_output.
        try:
            record.tokens_in = len(prompt.split())
            record.tokens_out = len(json.dumps(result.model_dump()).split())
        except Exception:
            pass
        self.provenance.add_call(record)
        _emit_llm_log(record, self._artifact_type)

        if not isinstance(result, schema):
            # Provider returned a dict-like — coerce & validate.
            try:
                result = schema.model_validate(result)
            except Exception as exc:
                raise ExternalServiceError(
                    f"Provider returned invalid structured output for "
                    f"{self._artifact_type}: {exc}"
                ) from exc
        return result


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


def _extract_content(result: Any) -> str:
    content = getattr(result, "content", result)
    if isinstance(content, list):
        return "\n".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content)


def _extract_token_usage(result: Any, prompt: str, content: str) -> tuple[Optional[int], Optional[int]]:
    # LangChain-standard usage_metadata on AIMessage.
    usage = getattr(result, "usage_metadata", None) or {}
    tokens_in = usage.get("input_tokens")
    tokens_out = usage.get("output_tokens")
    if tokens_in is None:
        tokens_in = len(prompt.split())
    if tokens_out is None:
        tokens_out = len(content.split())
    return tokens_in, tokens_out


def _bind_structured_output(chain: Any, schema: Type[BaseModel]) -> Any:
    """Attach structured-output mode to a LangChain model.

    Provider-native modes (in order of preference):
    - OpenAI / OpenRouter: json_schema with strict=True
    - Anthropic: tool-use
    - Gemini: response_schema

    LangChain's ``with_structured_output`` picks the right mode per provider
    if available, so we defer to it and fall back to tool-use for anything
    that doesn't support json_schema.
    """
    try:
        return chain.with_structured_output(schema, method="json_schema", strict=True)
    except Exception:
        pass
    try:
        return chain.with_structured_output(schema, method="function_calling")
    except Exception:
        pass
    return chain.with_structured_output(schema)


def _validate_schema(raw: str, schema: Type[BaseModel]) -> BaseModel:
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        return schema.model_validate(data)
    except Exception as exc:
        raise ExternalServiceError(
            f"Injected generator returned invalid payload for {schema.__name__}: {exc}"
        ) from exc


def _provider_from_chain(chain: Any) -> Optional[str]:
    # LangChain naming is inconsistent across providers; try a few fields.
    for attr in ("_llm_type", "provider", "_provider"):
        value = getattr(chain, attr, None)
        if value:
            return str(value).lower()
    cls_name = type(chain).__name__.lower()
    for provider in (
        "anthropic",
        "openai",
        "gemini",
        "google",
        "openrouter",
        "mistral",
        "deepseek",
        "xai",
        "groq",
        "ollama",
    ):
        if provider in cls_name:
            return provider
    return None


def _model_name_from_chain(chain: Any) -> Optional[str]:
    for attr in ("model_name", "model", "_model_name"):
        value = getattr(chain, attr, None)
        if value:
            return str(value)
    return None


def _emit_llm_log(record: LLMCallRecord, artifact_type: str) -> None:
    """Structured log line for observability.

    Tests assert this line is emitted; see plan §Observability.
    """
    payload = {
        "artifact_type": artifact_type,
        "attempt": record.attempt,
        "provider": record.provider,
        "model": record.model,
        "tokens_in": record.tokens_in,
        "tokens_out": record.tokens_out,
        "latency_ms": record.latency_ms,
        "prompt_hash": record.prompt_hash,
        "status": record.status,
        "error_class": record.error_class,
    }
    logger.bind(artifact_llm_call=True).info(json.dumps(payload))


# ----------------------------------------------------------------------
# Test utilities (kept: injected generators are still useful for pure unit
# tests that exercise prompt/schema shape, but they ALWAYS record provenance
# and cannot be used to bypass the real-LLM guard in integration tests).
# ----------------------------------------------------------------------


def make_static_generator(payload: Dict[str, Any]) -> TextGenerator:
    """Return a TextGenerator that echoes ``payload`` as JSON. Unit-test only."""

    async def _gen(_prompt: str) -> str:
        return json.dumps(payload)

    return _gen


def make_echo_generator(func: Callable[[str], Dict[str, Any]]) -> TextGenerator:
    """Return a TextGenerator that runs ``func`` on the prompt. Unit-test only."""

    async def _gen(prompt: str) -> str:
        return json.dumps(func(prompt))

    return _gen


def combine_prompts(instructions: str, context: str) -> str:
    """Build the canonical ``instructions\\n\\n# INPUT\\n\\n<context>`` layout."""
    return f"{instructions.strip()}\n\n# INPUT\n\n{context.strip()}"
