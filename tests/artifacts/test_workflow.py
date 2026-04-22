"""Tests for the multi-step workflow primitives."""
from __future__ import annotations

import pytest

from open_notebook.artifacts import ArtifactLLM, StructuredMockChat, schemas as S
from open_notebook.artifacts.workflow import (
    claims_to_context,
    draft_and_refine,
    extract_claims,
)


SOURCE = """Title: Refinery pipeline.
The team built a four-stage pipeline: plan, extract, draft, refine.
The refine pass uses self-critique against the original claims.
Benchmark: 85% of outputs improve after refinement. Published Q3 2024."""


@pytest.mark.asyncio
async def test_extract_claims_populates_all_fields():
    llm = ArtifactLLM(chat=StructuredMockChat())
    cs = await extract_claims(llm, SOURCE, focus="study guide")
    assert cs.topic
    assert cs.purpose
    assert len(cs.claims) >= 5
    assert cs.numeric_facts  # "85%", "Q3" should be there


@pytest.mark.asyncio
async def test_claims_to_context_renders_structured_block():
    llm = ArtifactLLM(chat=StructuredMockChat())
    cs = await extract_claims(llm, SOURCE)
    rendered = claims_to_context(cs, max_claims=5)
    assert "TOPIC:" in rendered
    assert "EXTRACTED CLAIMS:" in rendered
    # Importance + category should appear as tags
    assert "[critical/" in rendered or "[high/" in rendered


@pytest.mark.asyncio
async def test_draft_and_refine_produces_valid_schema():
    llm = ArtifactLLM(chat=StructuredMockChat())
    cs = await extract_claims(llm, SOURCE)
    context = claims_to_context(cs)
    briefing = await draft_and_refine(
        llm,
        schema=S.Briefing,
        draft_system="You are an analyst.",
        context=context,
        quality_floor=7,
        max_passes=1,
    )
    assert isinstance(briefing, S.Briefing)
    assert briefing.bluf
