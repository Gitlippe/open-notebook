"""Tests for the deterministic heuristic extractor."""
from __future__ import annotations

from open_notebook.artifacts.heuristic import (
    extract_dates,
    extract_input_block,
    extract_title,
    heuristic_json,
    keywords,
    rank_sentences,
    split_sentences,
)


def test_split_sentences_basic():
    text = "First sentence. Second sentence! Third one? Fourth."
    assert split_sentences(text) == [
        "First sentence.",
        "Second sentence!",
        "Third one?",
        "Fourth.",
    ]


def test_keywords_filters_stopwords():
    text = "the quick brown fox jumps over the lazy dog. the fox is quick and clever."
    kws = keywords(text, top_n=3)
    assert "the" not in kws
    assert "quick" in kws or "fox" in kws


def test_rank_sentences_returns_subset():
    text = " ".join(f"Sentence {i}." for i in range(10))
    picked = rank_sentences(text, top_n=3)
    assert len(picked) == 3
    assert all(s in split_sentences(text) for s in picked)


def test_extract_input_block_strips_metadata_headers():
    prompt = """
# INPUT

SOURCE: My Paper
AUTHOR: Someone
DATE: 2024
URL: https://example.com

Body sentence.
"""
    out = extract_input_block(prompt)
    assert "SOURCE:" not in out
    assert "AUTHOR:" not in out
    assert "Body sentence" in out


def test_extract_title_prefers_title_line():
    text = "Title: Clean Title\nBody content here."
    assert extract_title(text) == "Clean Title"


def test_extract_dates_finds_years_and_iso():
    text = "This happened in 2020. Then in March 2022 something else. On 2023-05-01 more."
    dates = extract_dates(text)
    labels = [d[0] for d in dates]
    assert any("2020" in label for label in labels)
    assert any("2023-05-01" in label for label in labels)


def test_heuristic_briefing_has_required_keys():
    data = heuristic_json(
        "prompt\n\n# INPUT\n\nA research paper discusses improving LLM agents.",
        artifact_type="briefing",
    )
    assert {"title", "bluf", "key_points", "supporting_details", "action_items"} <= data.keys()


def test_heuristic_quiz_has_valid_answer_index():
    data = heuristic_json(
        "prompt\n\n# INPUT\n\nSome content about AI safety and alignment.",
        artifact_type="quiz",
    )
    for q in data["questions"]:
        assert 0 <= q["answer_index"] < len(q["options"])


def test_heuristic_mindmap_structure():
    data = heuristic_json(
        "prompt\n\n# INPUT\n\nAlpha, beta, gamma. The study of alpha and beta.",
        artifact_type="mindmap",
    )
    assert "central_topic" in data
    assert isinstance(data["branches"], list)
    assert all("label" in b for b in data["branches"])
