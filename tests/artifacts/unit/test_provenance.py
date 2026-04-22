"""Provenance contract tests — no real LLM required.

These tests prove the provenance scaffolding is wired correctly so that
downstream integration tests can rely on ``ArtifactResult.provenance`` to
distinguish real LLM calls from fakes.
"""
from __future__ import annotations

import json

import pytest

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    ArtifactSource,
)
from open_notebook.artifacts.llm import (
    ArtifactLLM,
    GenerationProvenance,
    LLMCallRecord,
    make_static_generator,
)


pytestmark = pytest.mark.unit


def test_generation_provenance_roundtrip() -> None:
    prov = GenerationProvenance(
        run_id="r1",
        artifact_type="briefing",
        model_id="anthropic/claude-sonnet-4-6",
    )
    prov.add_call(
        LLMCallRecord(
            prompt_hash="abc123",
            tokens_in=100,
            tokens_out=50,
            latency_ms=120,
            attempt=1,
            provider="anthropic",
            model="claude-sonnet-4-6",
        )
    )
    dumped = prov.model_dump()
    restored = GenerationProvenance.model_validate(dumped)
    assert restored.run_id == "r1"
    assert restored.calls[0].provider == "anthropic"
    assert restored.calls[0].tokens_out == 50


def test_artifact_result_carries_provenance() -> None:
    prov = GenerationProvenance(run_id="r1", artifact_type="briefing")
    prov.add_call(LLMCallRecord(prompt_hash="x"))
    result = ArtifactResult(
        artifact_type="briefing",
        title="t",
        provenance=prov,
        files=[ArtifactFile(path="/tmp/x.md", mime_type="text/markdown")],
    )
    dumped = result.model_dump()
    assert dumped["provenance"]["calls"][0]["prompt_hash"] == "x"
    restored = ArtifactResult.model_validate(dumped)
    assert restored.provenance is not None
    assert len(restored.provenance.calls) == 1


@pytest.mark.asyncio
async def test_injected_generator_records_call() -> None:
    """Even test-injected generators must record a provenance entry.

    This prevents a tempting shortcut: 'I'll inject a fake so my test passes
    without a real LLM'. The provenance still says ``provider=injected``, and
    integration tests assert provider is in the live-provider allowlist.
    """
    gen = make_static_generator({"summary": "ok", "key_points": ["a"]})
    llm = ArtifactLLM(text_generator=gen, artifact_type="briefing")
    out = await llm.generate_text("hello")
    assert out == json.dumps({"summary": "ok", "key_points": ["a"]})
    assert len(llm.provenance.calls) == 1
    assert llm.provenance.calls[0].provider == "injected"


def test_combined_content_does_not_truncate() -> None:
    """Verify the old max_chars truncation is gone at runtime (not just AST)."""
    src = ArtifactSource(title="big", content="x" * 50_000)
    req = ArtifactRequest(artifact_type="briefing", sources=[src])
    combined = req.combined_content()
    assert len(combined) >= 50_000, (
        "combined_content must return full-fidelity content; long inputs "
        "should go through chunked_generate() instead of being truncated."
    )
