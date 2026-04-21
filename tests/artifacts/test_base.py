"""Tests for base artifact data structures and registry."""
from __future__ import annotations

import pytest

from open_notebook.artifacts import (
    ARTIFACT_TYPES,
    ArtifactRequest,
    ArtifactSource,
    generate_artifact,
    get_generator,
    list_artifact_types,
)


def test_all_expected_types_registered():
    expected = {
        "briefing",
        "study_guide",
        "faq",
        "research_review",
        "flashcards",
        "quiz",
        "mindmap",
        "timeline",
        "infographic",
        "slide_deck",
        "pitch_deck",
        "paper_figure",
    }
    assert expected.issubset(ARTIFACT_TYPES.keys())


def test_list_artifact_types_returns_records():
    records = list_artifact_types()
    assert len(records) >= 12
    for record in records:
        assert "type" in record and "description" in record


def test_get_generator_unknown_type_raises():
    with pytest.raises(KeyError):
        get_generator("nonexistent-type")


def test_source_to_context_block_includes_metadata():
    src = ArtifactSource(
        title="Paper",
        content="Body",
        author="Alice",
        published_at="2024",
        url="https://x.test",
    )
    block = src.to_context_block()
    assert "SOURCE: Paper" in block
    assert "AUTHOR: Alice" in block
    assert "DATE: 2024" in block
    assert "URL: https://x.test" in block


def test_request_fingerprint_deterministic():
    req = ArtifactRequest(
        artifact_type="briefing",
        title="T",
        sources=[ArtifactSource(title="a", content="b")],
        config={"k": 1},
    )
    assert req.fingerprint() == req.fingerprint()
    assert len(req.fingerprint()) == 10


def test_combined_content_truncation():
    req = ArtifactRequest(
        artifact_type="briefing",
        sources=[ArtifactSource(title="t", content="word " * 500)],
    )
    truncated = req.combined_content(max_chars=100)
    assert len(truncated) <= 200
    assert "truncated" in truncated


@pytest.mark.asyncio
async def test_generate_artifact_requires_sources(output_dir):
    with pytest.raises(Exception):
        await generate_artifact("briefing", [], output_dir=output_dir)
