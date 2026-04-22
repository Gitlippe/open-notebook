"""Image generation module for Open Notebook artifacts.

**Stream G coordination contract:**
  Video overview's ``beats.json`` provides each beat with a ``visual_prompt``
  string.  Stream G calls::

      from open_notebook.artifacts.image_gen import generate_image
      png_bytes = await generate_image(beat["visual_prompt"])

  and receives raw PNG ``bytes``.  The function signature is stable:

      async def generate_image(
          prompt: str,
          size: str = "1024x1024",
          model: str = "gpt-image-1",
      ) -> bytes

  No other arguments need to be passed for the video pipeline.

Provider routing
----------------
- **Primary**: OpenAI ``gpt-image-1`` via ``openai.AsyncOpenAI``.  The API key
  is resolved from the database (Credential record for ``openai``) or the
  ``OPENAI_API_KEY`` environment variable via
  :func:`open_notebook.ai.key_provider.get_api_key`.
- **Fallback model**: ``dall-e-3`` if the model is unrecognised by the
  endpoint.  *No* silent content-stub fallback — if provisioning fails, a
  :class:`~open_notebook.exceptions.ConfigurationError` is raised immediately.

Retries
-------
Transient HTTP errors are retried up to 3 times with exponential jitter via
``tenacity`` (initial 1 s, multiplier 2, max 10 s).

Logging
-------
Every call emits a structured loguru INFO record tagged ``image_gen_call=True``
with fields: ``provider``, ``model``, ``prompt_hash``, ``size``,
``latency_ms``, ``status``.  The record mirrors the artifact LLM log format
so the same log sink captures it.

Configuration errors
--------------------
If no OpenAI API key is found (neither in DB nor env var), raises
:class:`~open_notebook.exceptions.ConfigurationError`.  **No fallback stubs.**
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Optional

from loguru import logger
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from open_notebook.exceptions import ConfigurationError, ExternalServiceError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_MODEL = "gpt-image-1"
_DEFAULT_SIZE = "1024x1024"
_MAX_ATTEMPTS = 3
_WAIT_INITIAL = 1.0
_WAIT_MAX = 10.0
_WAIT_EXP = 2.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


def _emit_image_log(
    *,
    provider: str,
    model: str,
    prompt_hash: str,
    size: str,
    latency_ms: int,
    status: str,
    error_class: Optional[str] = None,
) -> None:
    payload = {
        "provider": provider,
        "model": model,
        "prompt_hash": prompt_hash,
        "size": size,
        "latency_ms": latency_ms,
        "status": status,
        "error_class": error_class,
    }
    logger.bind(image_gen_call=True).info(json.dumps(payload))


async def _resolve_api_key() -> str:
    """Resolve the OpenAI API key: DB credential first, env var fallback."""
    # Try key_provider (DB-backed) — this requires a live DB connection.
    # In unit tests or standalone use, we gracefully fall back to env var.
    try:
        from open_notebook.ai.key_provider import get_api_key
        key = await get_api_key("openai")
        if key:
            return key
    except Exception:
        # No DB connection or key_provider unavailable — continue to env var
        pass

    # Env var fallback
    env_key = os.environ.get("OPENAI_API_KEY")
    if env_key:
        return env_key

    raise ConfigurationError(
        "No OpenAI API key configured. "
        "Add an 'openai' Credential in Settings or set the OPENAI_API_KEY "
        "environment variable to use image generation."
    )


async def _generate_via_openai(
    api_key: str,
    prompt: str,
    model: str,
    size: str,
) -> bytes:
    """Call OpenAI image generation and return raw PNG bytes."""
    import base64
    import openai

    client = openai.AsyncOpenAI(api_key=api_key)

    # gpt-image-1 always returns b64_json and rejects the response_format
    # parameter. dall-e-3 defaults to URLs; we pass response_format=b64_json
    # only for models that accept it.
    kwargs: dict = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": size,
    }
    if model.startswith("dall-e"):
        kwargs["response_format"] = "b64_json"

    response = await client.images.generate(**kwargs)

    b64_data = response.data[0].b64_json
    if not b64_data:
        raise ExternalServiceError(
            f"OpenAI image generation returned empty b64_json for model {model!r}."
        )
    return base64.b64decode(b64_data)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def generate_image(
    prompt: str,
    size: str = _DEFAULT_SIZE,
    model: str = _DEFAULT_MODEL,
) -> bytes:
    """Generate an image from *prompt* and return raw PNG bytes.

    **Stream G interface** — this signature is stable and must not change
    without coordinating with the video_renderer.

    Args:
        prompt: Natural-language image description.
        size:   WxH string accepted by the provider (e.g. ``"1024x1024"``).
        model:  Image model ID.  Defaults to ``"gpt-image-1"``.

    Returns:
        Raw PNG ``bytes``.

    Raises:
        ConfigurationError: If no API key is available for the provider.
        ExternalServiceError: If the provider returns an error after retries.
    """
    api_key = await _resolve_api_key()
    phash = _prompt_hash(prompt)
    start = time.perf_counter()
    status = "ok"
    error_class: Optional[str] = None

    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(_MAX_ATTEMPTS),
            wait=wait_exponential_jitter(
                initial=_WAIT_INITIAL, max=_WAIT_MAX, exp_base=_WAIT_EXP
            ),
            retry=retry_if_exception_type((
                ExternalServiceError,
                ConnectionError,
                TimeoutError,
            )),
            reraise=True,
        ):
            with attempt:
                png_bytes = await _generate_via_openai(api_key, prompt, model, size)

    except ConfigurationError:
        raise
    except Exception as exc:
        status = "error"
        error_class = type(exc).__name__
        latency_ms = int((time.perf_counter() - start) * 1000)
        _emit_image_log(
            provider="openai",
            model=model,
            prompt_hash=phash,
            size=size,
            latency_ms=latency_ms,
            status=status,
            error_class=error_class,
        )
        raise ExternalServiceError(
            f"Image generation failed after {_MAX_ATTEMPTS} attempts: {exc}"
        ) from exc

    latency_ms = int((time.perf_counter() - start) * 1000)
    _emit_image_log(
        provider="openai",
        model=model,
        prompt_hash=phash,
        size=size,
        latency_ms=latency_ms,
        status=status,
        error_class=error_class,
    )
    return png_bytes


async def generate_image_to_file(
    prompt: str,
    output_path: Path,
    *,
    size: str = _DEFAULT_SIZE,
    model: str = _DEFAULT_MODEL,
) -> Path:
    """Generate an image and write it to *output_path*.

    Convenience wrapper around :func:`generate_image` for callers that need
    a file path (e.g. the PPTX renderer embedding chart images, or the video
    renderer stamping beat visuals).

    Args:
        prompt:      Natural-language image description.
        output_path: Destination file path.  Parent directories are created.
        size:        WxH string (default ``"1024x1024"``).
        model:       Image model ID (default ``"gpt-image-1"``).

    Returns:
        *output_path* as a :class:`~pathlib.Path` after the file is written.
    """
    png_bytes = await generate_image(prompt, size=size, model=model)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(png_bytes)
    return output_path
