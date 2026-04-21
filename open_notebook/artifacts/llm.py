"""Unified LLM adapter for artifact generation.

Provides a single interface that:

1. Prefers an explicitly injected async callable (useful for tests).
2. Uses ``open_notebook.ai.provision.provision_langchain_model`` when AI
   credentials are available (so production users get full LLM output).
3. Falls back to a deterministic heuristic extractor that produces
   reasonable structured output from raw text. This keeps the artifact
   generation pipeline fully functional during local development, tests,
   and demos even without any API keys.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional

from loguru import logger

from open_notebook.artifacts.heuristic import heuristic_json

TextGenerator = Callable[[str], Awaitable[str]]


class ArtifactLLM:
    """Thin facade over the repo's AI provisioning with a safe fallback."""

    def __init__(
        self,
        text_generator: Optional[TextGenerator] = None,
        default_type: str = "transformation",
        model_id: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> None:
        self._text_generator = text_generator
        self._default_type = default_type
        self._model_id = model_id
        self._max_tokens = max_tokens

    # ------------------------------------------------------------------
    # Dispatchers
    # ------------------------------------------------------------------
    async def generate_text(self, prompt: str) -> str:
        """Return free-form text from the LLM (or a heuristic summary)."""
        if self._text_generator is not None:
            return await self._text_generator(prompt)

        if self._can_use_langchain():
            try:
                return await self._langchain_text(prompt)
            except Exception as exc:  # pragma: no cover - provider errors
                logger.warning(
                    "ArtifactLLM provision_langchain_model failed, "
                    f"falling back to heuristic: {exc}"
                )

        return _heuristic_text(prompt)

    async def generate_json(
        self,
        prompt: str,
        schema_hint: Optional[Dict[str, Any]] = None,
        artifact_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return a JSON dict from the LLM.

        Tolerant of pre/post chatter around the JSON payload. Falls back to
        a deterministic heuristic when the LLM is unavailable or returns
        unparseable output.
        """
        text = await self.generate_text(prompt)
        data = _parse_json_loose(text)
        if data is None:
            return heuristic_json(
                prompt,
                schema_hint=schema_hint,
                artifact_type=artifact_type,
            )
        return data

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _can_use_langchain(self) -> bool:
        """Decide whether to even attempt LLM provisioning.

        Requires both:
        - At least one provider env var set.
        - The runtime has been opted in via ``ARTIFACT_USE_LLM=1``. We gate on
          an explicit flag because ``provision_langchain_model`` reads model
          defaults from SurrealDB; when no DB is running (tests / CI / demo)
          the first call raises and we would spam warnings needlessly.
        """
        if os.environ.get("ARTIFACT_USE_LLM", "0") not in {"1", "true", "yes", "on"}:
            return False
        env_keys = (
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GROQ_API_KEY",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
            "MISTRAL_API_KEY",
            "DEEPSEEK_API_KEY",
            "XAI_API_KEY",
            "OLLAMA_BASE_URL",
        )
        if not any(os.environ.get(k) for k in env_keys):
            return False
        try:
            import open_notebook.ai.provision  # noqa: F401
        except Exception:  # pragma: no cover - provisioning missing
            return False
        return True

    async def _langchain_text(self, prompt: str) -> str:
        from langchain_core.messages import HumanMessage

        from open_notebook.ai.provision import provision_langchain_model

        chain = await provision_langchain_model(
            prompt,
            self._model_id,
            self._default_type,
            max_tokens=self._max_tokens,
        )
        result = await chain.ainvoke([HumanMessage(content=prompt)])
        content = getattr(result, "content", result)
        if isinstance(content, list):
            return "\n".join(
                block.get("text", "") if isinstance(block, dict) else str(block)
                for block in content
            )
        return str(content)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _parse_json_loose(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except Exception:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", stripped, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except Exception:
            pass

    first_brace = stripped.find("{")
    last_brace = stripped.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidate = stripped[first_brace : last_brace + 1]
        try:
            return json.loads(candidate)
        except Exception:
            return None
    return None


def _heuristic_text(prompt: str) -> str:
    """Return a short plain-text summary of the prompt's payload.

    Used only when neither an LLM nor an injected generator is available.
    """
    body = prompt.split("# INPUT", 1)[-1]
    body = re.sub(r"\s+", " ", body).strip()
    if len(body) < 400:
        return body
    return body[:400] + "..."


def make_static_generator(payload: Dict[str, Any]) -> TextGenerator:
    """Factory: build a ``TextGenerator`` that always returns ``payload`` as JSON.

    Useful in tests where you want the LLM to return a canned response.
    """

    async def _gen(_prompt: str) -> str:
        return json.dumps(payload)

    return _gen


def make_echo_generator(func: Callable[[str], Dict[str, Any]]) -> TextGenerator:
    """Factory: run an arbitrary sync function on the prompt and JSON-encode it."""

    async def _gen(prompt: str) -> str:
        return json.dumps(func(prompt))

    return _gen


def combine_prompts(instructions: str, context: str) -> str:
    """Build the canonical ``instructions\\n\\n# INPUT\\n\\n<context>`` layout."""
    return f"{instructions.strip()}\n\n# INPUT\n\n{context.strip()}"
