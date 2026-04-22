"""Tests for the ArtifactLLM facade."""
from __future__ import annotations

import pytest

from open_notebook.artifacts import (
    ArtifactLLM,
    StructuredMockChat,
    schemas as S,
    use_artifact_llm,
)


@pytest.mark.asyncio
async def test_artifact_llm_wraps_chat():
    llm = ArtifactLLM(chat=StructuredMockChat())
    result = await llm.structured(
        system_prompt="Briefing please.",
        user_prompt="Title: demo. Widgets shipped 42 this quarter.",
        schema=S.Briefing,
    )
    assert isinstance(result, S.Briefing)
    assert len(result.key_points) >= 3


@pytest.mark.asyncio
async def test_use_artifact_llm_contextvar():
    override = ArtifactLLM(chat=StructuredMockChat())
    assert ArtifactLLM.current() is not override
    with use_artifact_llm(override):
        assert ArtifactLLM.current() is override
    assert ArtifactLLM.current() is not override


@pytest.mark.asyncio
async def test_structured_output_matches_schema_types():
    llm = ArtifactLLM(chat=StructuredMockChat())
    quiz = await llm.structured(
        system_prompt="Quiz please.",
        user_prompt="Title: demo. Concept A and Concept B. Concept A is foo. Concept B is bar.",
        schema=S.Quiz,
    )
    for q in quiz.questions:
        assert len(q.options) == 4
        assert 0 <= q.answer_index <= 3
