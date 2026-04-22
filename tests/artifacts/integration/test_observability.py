"""Observability contract tests.

Per the plan (§ Observability), every LLM call in ``ArtifactLLM`` must emit
one structured loguru record with these fields:

    ts, run_id, artifact_type, attempt_num, provider, model,
    tokens_in, tokens_out, latency_ms, prompt_hash, status, error_class

This test captures loguru output during a minimal real-LLM call and asserts
the contract. If the logging shape breaks, dashboards and alerts relying on
artifact_llm_call telemetry go dark — so we gate on it.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from loguru import logger

from open_notebook.artifacts.base import ArtifactRequest, ArtifactSource
from open_notebook.artifacts.registry import get_generator

from .conftest import best_langchain_model, has_provider_key

pytestmark = [pytest.mark.integration, pytest.mark.real_llm]

REQUIRED_FIELDS = {
    "artifact_type",
    "attempt",
    "provider",
    "model",
    "tokens_in",
    "tokens_out",
    "latency_ms",
    "prompt_hash",
    "status",
}


@pytest.fixture
def captured_llm_logs():
    """Collect every INFO record tagged ``artifact_llm_call=True``."""
    records: list[dict] = []

    def sink(message):  # loguru sinks are callables
        record = message.record
        extra = record.get("extra", {})
        if not extra.get("artifact_llm_call"):
            return
        try:
            payload = json.loads(record["message"])
        except Exception:
            return
        records.append(payload)

    sink_id = logger.add(sink, level="INFO")
    try:
        yield records
    finally:
        logger.remove(sink_id)


async def test_every_call_logged(captured_llm_logs, tmp_path) -> None:
    """Runs a briefing generation and asserts one structured log per LLM call."""
    if not has_provider_key():
        pytest.skip("no provider keys set — can't exercise observability contract")

    real_model = best_langchain_model()

    generator = get_generator("briefing")
    request = ArtifactRequest(
        artifact_type="briefing",
        title="observability-probe",
        sources=[
            ArtifactSource(
                title="Sample",
                content=(
                    "Observability should be cheap to emit and expensive to omit. "
                    "Every LLM call carries latency and token counts that drive "
                    "the dashboards oncall watches."
                ),
            )
        ],
        output_dir=str(tmp_path),
    )

    with patch(
        "open_notebook.ai.provision.provision_langchain_model",
        new=AsyncMock(return_value=real_model),
    ):
        result = await generator.generate(request)

    # At least one log record was emitted.
    assert captured_llm_logs, (
        "No artifact_llm_call log records captured — either the generator did "
        "not invoke the LLM, or the logger.bind(artifact_llm_call=True) wiring "
        "has regressed."
    )

    # Log count matches provenance call count — they should be 1:1.
    assert len(captured_llm_logs) == len(result.provenance.calls), (
        f"Log/provenance mismatch: {len(captured_llm_logs)} logs vs "
        f"{len(result.provenance.calls)} provenance calls. Either a call was "
        "logged but not recorded in provenance, or vice versa."
    )

    for entry in captured_llm_logs:
        missing = REQUIRED_FIELDS - set(entry)
        assert not missing, f"Log entry missing required fields: {sorted(missing)} — got {entry}"
        assert entry["provider"], f"provider field is empty: {entry}"
        assert entry["model"], f"model field is empty: {entry}"
        assert entry["status"] == "ok", f"non-ok status in log: {entry}"
        # latency_ms must be a non-negative integer.
        assert isinstance(entry["latency_ms"], int) and entry["latency_ms"] >= 0
        # tokens_out must be positive (empty output = failed call).
        assert (entry["tokens_out"] or 0) > 0, f"tokens_out not positive: {entry}"
