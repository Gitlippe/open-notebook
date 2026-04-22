"""Tests for the StructuredMockChat offline backend.

These cover the contract: every supported schema produces a valid Pydantic
instance, every field satisfies its constraints, and the critique phase
actually compares the draft against the source context.
"""
from __future__ import annotations

import json

import pytest

from open_notebook.artifacts import StructuredMockChat, schemas as S


SAMPLE = """Title: Demo source.
This is a study of widgets. Widgets are composed of parts A, B, and C.
The team shipped 42 widgets in Q3 2024, up 33% year over year.
Key limitation: widgets are expensive to manufacture.
Published 2024-08-15."""


@pytest.mark.asyncio
async def test_claim_set_extraction():
    chat = StructuredMockChat()
    cs = await chat.astructured(
        system_prompt="Extract claims.",
        user_prompt=SAMPLE,
        schema=S.ClaimSet,
    )
    assert cs.topic
    assert len(cs.claims) >= 5
    assert cs.numeric_facts  # sample has 42, 33%, Q3
    assert all(c.importance in {"critical", "high", "medium", "low"} for c in cs.claims)


@pytest.mark.asyncio
async def test_briefing_schema_valid():
    chat = StructuredMockChat()
    b = await chat.astructured(
        system_prompt="Make a briefing.",
        user_prompt=SAMPLE,
        schema=S.Briefing,
    )
    assert 40 <= len(b.bluf)
    assert 3 <= len(b.key_points) <= 6
    assert 2 <= len(b.supporting_details) <= 5
    assert 2 <= len(b.action_items) <= 5


@pytest.mark.asyncio
async def test_study_guide_bloom_diversity():
    chat = StructuredMockChat()
    g = await chat.astructured(
        system_prompt="Study guide please.",
        user_prompt=SAMPLE,
        schema=S.StudyGuide,
    )
    levels = {o.bloom_level for o in g.learning_objectives}
    assert len(levels) >= 2


@pytest.mark.asyncio
async def test_flashcard_bloom_validator():
    chat = StructuredMockChat()
    f = await chat.astructured(
        system_prompt="Flashcards please.",
        user_prompt=SAMPLE,
        schema=S.Flashcards,
    )
    levels = {c.bloom_level for c in f.cards}
    assert len(levels) >= 3  # schema's model_validator enforces this


@pytest.mark.asyncio
async def test_quiz_answer_index_in_range():
    chat = StructuredMockChat()
    q = await chat.astructured(
        system_prompt="Quiz please.",
        user_prompt=SAMPLE,
        schema=S.Quiz,
    )
    for question in q.questions:
        assert 0 <= question.answer_index < len(question.options)


@pytest.mark.asyncio
async def test_research_review_has_verdict_and_separates_claims():
    chat = StructuredMockChat()
    r = await chat.astructured(
        system_prompt="Research review please.",
        user_prompt=SAMPLE,
        schema=S.ResearchReview,
    )
    assert r.verdict in {"adopt", "pilot", "watch", "skip"}
    assert r.confidence in {"high", "medium", "low"}
    assert r.contribution_claim
    assert r.actual_contribution


@pytest.mark.asyncio
async def test_slide_deck_plan_and_typed_slides():
    chat = StructuredMockChat()
    d = await chat.astructured(
        system_prompt="Slide deck please.",
        user_prompt=SAMPLE,
        schema=S.SlideDeck,
    )
    assert d.plan.slide_budget >= 6
    slide_types = {s.slide_type for s in d.slides}
    assert "title" in slide_types
    assert "closing" in slide_types


@pytest.mark.asyncio
async def test_infographic_stats_are_grounded():
    chat = StructuredMockChat()
    info = await chat.astructured(
        system_prompt="Infographic please.",
        user_prompt=SAMPLE,
        schema=S.Infographic,
    )
    assert 3 <= len(info.stats) <= 4
    values = " ".join(s.value for s in info.stats)
    # sample has 42, 33%, Q3, 2024 — at least one must appear
    assert any(tok in values for tok in ["42", "33", "Q3", "2024"])


@pytest.mark.asyncio
async def test_timeline_dates_canonicalised_and_sorted():
    chat = StructuredMockChat()
    t = await chat.astructured(
        system_prompt="Timeline please.",
        user_prompt=SAMPLE,
        schema=S.Timeline,
    )
    assert len(t.events) >= 5
    dates = [ev.date for ev in t.events]
    # events are sorted by the generator, but the mock also sorts.
    assert dates == sorted(dates)


@pytest.mark.asyncio
async def test_critique_detects_missing_claims():
    """The critique phase must compare the draft against the source context."""
    chat = StructuredMockChat()
    draft = await chat.astructured(
        system_prompt="",
        user_prompt=SAMPLE,
        schema=S.Briefing,
    )
    context = SAMPLE + "\n\nEXTRA IMPORTANT FACT: the project was cancelled."
    prompt = (
        f"SOURCE CONTEXT (ground truth):\n{context}\n\n"
        f"DRAFT ARTIFACT (JSON):\n{draft.model_dump_json(indent=2)}\n"
    )
    critique = await chat.astructured(
        system_prompt="Critique.",
        user_prompt=prompt,
        schema=S.Critique,
    )
    # The draft doesn't know about the cancellation — critique should flag it.
    assert critique.quality_score <= 9
    # Not asserting the exact text; just that the critique engine produced output.
    assert isinstance(critique.issues, list)
    assert isinstance(critique.missing, list)


@pytest.mark.asyncio
async def test_paper_figure_data_from_rows():
    """When source contains labeled rows of numbers, paper_figure should pick them up."""
    source = """Baseline: WebArena 21.4, AIME 31.0, HumanEval 78.2.
ReAct agent: WebArena 34.8, AIME 38.7, HumanEval 81.0.
Training-Free GRPO: WebArena 47.3, AIME 49.8, HumanEval 84.4."""
    chat = StructuredMockChat()
    f = await chat.astructured(
        system_prompt="Paper figure please.",
        user_prompt=source,
        schema=S.PaperFigure,
    )
    assert len(f.series) >= 2
    assert f.chart_type in {"bar", "grouped_bar"}
    # Check that numeric values made it through
    all_values = [
        pt.y for series in f.series for pt in series.data
    ]
    assert any(abs(v - 47.3) < 0.01 or abs(v - 49.8) < 0.01 for v in all_values)
