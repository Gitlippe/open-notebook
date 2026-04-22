"""Integration tests for markdown renderer — no real LLM calls.

Tests verify:
  - render_briefing: BLUF callout present; GFM horizontal rules; key sections.
  - render_study_guide: glossary GFM table produced; learning objectives numbered.
  - render_faq: Q&A format correct; item count matches.
  - render_quiz: options lettered; correct-answer marker present.
  - render_timeline: GFM table with Date/Event/Significance columns.
  - render_mindmap: section headings + bullets.
  - render_research_review: BLUF callout + resource links.
  - write(): file written correctly.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def briefing_data():
    return {
        "title": "Q3 Strategy Briefing",
        "audience": "Executive team",
        "bluf": "We must ship by end of quarter.",
        "key_points": ["Alpha", "Beta"],
        "supporting_details": ["Stat 1", "Stat 2"],
        "action_items": ["Ship it", "Hire 3 engineers"],
        "keywords": ["strategy", "q3"],
    }


@pytest.fixture
def study_guide_data():
    return {
        "title": "Study Guide: Python",
        "overview": "Core Python programming concepts.",
        "learning_objectives": ["Understand lists", "Use dicts effectively"],
        "key_concepts": ["List comprehension", "Dictionary"],
        "glossary": [
            {"term": "Iterator", "definition": "Object yielding items one at a time."},
            {"term": "Generator", "definition": "Function that yields values lazily."},
        ],
        "discussion_questions": ["When to use a list vs a set?"],
        "further_reading": ["https://docs.python.org", "Fluent Python by Ramalho"],
    }


@pytest.fixture
def faq_data():
    return {
        "title": "FAQ: Python Basics",
        "items": [
            {"question": "Is Python interpreted?", "answer": "Yes."},
            {"question": "What is a list?", "answer": "An ordered mutable sequence."},
            {"question": "What is GIL?", "answer": "Global Interpreter Lock."},
        ],
    }


@pytest.fixture
def quiz_data():
    return {
        "title": "Quiz: Python",
        "questions": [
            {
                "question": "What does list() do?",
                "options": ["Creates list", "Deletes list", "Sorts list", "Reverses list"],
                "answer_index": 0,
                "explanation": "list() creates a new list object.",
            },
            {
                "question": "Which is mutable?",
                "options": ["tuple", "str", "list", "frozenset"],
                "answer_index": 2,
                "explanation": "Lists support item assignment.",
            },
        ],
    }


@pytest.fixture
def timeline_data():
    return {
        "title": "Timeline: Python History",
        "events": [
            {"date": "1991", "event": "Python 0.9 released", "significance": "First public version."},
            {"date": "2008", "event": "Python 3.0 released", "significance": "Major redesign."},
            {"date": "2020", "event": "Python 2 EOL", "significance": "End of legacy support."},
        ],
    }


@pytest.fixture
def mindmap_data():
    return {
        "central_topic": "Python",
        "branches": [
            {"label": "Data Types", "children": ["list", "dict", "set"]},
            {"label": "Control Flow", "children": ["if", "for", "while"]},
        ],
    }


@pytest.fixture
def research_review_data():
    return {
        "title": "Research Review: Training-Free GRPO",
        "bluf": "Skeptical but interesting approach.",
        "notable_authors": ["Cai", "Smith"],
        "affiliations": ["Tencent", "MIT"],
        "short_take": "Prompt-only RL optimisation without parameter updates.",
        "why_we_care": {"direct_techniques": ["prompting", "RL"]},
        "limitations": ["No head-to-head comparison"],
        "potential_applications": ["Low-cost fine-tuning"],
        "resources": [{"label": "arXiv", "url": "https://arxiv.org/abs/1234"}],
    }


# ---------------------------------------------------------------------------
# render_briefing
# ---------------------------------------------------------------------------

def test_briefing_has_title(briefing_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_briefing
    md = render_briefing(briefing_data)
    assert "# Q3 Strategy Briefing" in md


def test_briefing_bluf_callout(briefing_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_briefing
    md = render_briefing(briefing_data)
    assert "> **BLUF:**" in md
    assert "We must ship by end of quarter" in md


def test_briefing_horizontal_rules(briefing_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_briefing
    md = render_briefing(briefing_data)
    assert "---" in md


def test_briefing_key_points(briefing_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_briefing
    md = render_briefing(briefing_data)
    assert "Key Points" in md
    assert "- Alpha" in md
    assert "- Beta" in md


def test_briefing_action_items_numbered(briefing_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_briefing
    md = render_briefing(briefing_data)
    assert "Action Items" in md
    assert "1. Ship it" in md


def test_briefing_keywords(briefing_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_briefing
    md = render_briefing(briefing_data)
    assert "strategy" in md
    assert "q3" in md


# ---------------------------------------------------------------------------
# render_study_guide
# ---------------------------------------------------------------------------

def test_study_guide_title(study_guide_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_study_guide
    md = render_study_guide(study_guide_data)
    assert "# Study Guide: Python" in md


def test_study_guide_gfm_glossary_table(study_guide_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_study_guide
    md = render_study_guide(study_guide_data)
    # GFM table: has | Term | Definition | header
    assert "| Term" in md or "| term" in md.lower()
    assert ":---" in md  # GFM separator


def test_study_guide_numbered_objectives(study_guide_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_study_guide
    md = render_study_guide(study_guide_data)
    assert "1. Understand lists" in md


def test_study_guide_further_reading_link(study_guide_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_study_guide
    md = render_study_guide(study_guide_data)
    assert "[https://docs.python.org](https://docs.python.org)" in md


def test_study_guide_sections_present(study_guide_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_study_guide
    md = render_study_guide(study_guide_data)
    for sec in ["Overview", "Learning Objectives", "Key Concepts", "Glossary", "Discussion Questions"]:
        assert sec in md, f"Missing section: {sec}"


# ---------------------------------------------------------------------------
# render_faq
# ---------------------------------------------------------------------------

def test_faq_title(faq_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_faq
    md = render_faq(faq_data)
    assert "# FAQ: Python Basics" in md


def test_faq_question_count(faq_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_faq
    md = render_faq(faq_data)
    # Three questions → Q1, Q2, Q3
    assert "Q1." in md
    assert "Q2." in md
    assert "Q3." in md


def test_faq_answers_present(faq_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_faq
    md = render_faq(faq_data)
    assert "Global Interpreter Lock" in md


# ---------------------------------------------------------------------------
# render_quiz
# ---------------------------------------------------------------------------

def test_quiz_title(quiz_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_quiz
    md = render_quiz(quiz_data)
    assert "# Quiz: Python" in md


def test_quiz_lettered_options(quiz_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_quiz
    md = render_quiz(quiz_data)
    assert "[A]" in md
    assert "[B]" in md
    assert "[C]" in md
    assert "[D]" in md


def test_quiz_correct_marker(quiz_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_quiz
    md = render_quiz(quiz_data)
    # Correct answer should have checkmark
    assert "✓" in md


def test_quiz_explanation_callout(quiz_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_quiz
    md = render_quiz(quiz_data)
    assert "> **Explanation:**" in md


# ---------------------------------------------------------------------------
# render_timeline
# ---------------------------------------------------------------------------

def test_timeline_title(timeline_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_timeline
    md = render_timeline(timeline_data)
    assert "# Timeline: Python History" in md


def test_timeline_gfm_table(timeline_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_timeline
    md = render_timeline(timeline_data)
    assert "| Date" in md or "| date" in md.lower()
    assert "| Event" in md or "| event" in md.lower()
    assert "| Significance" in md or "| significance" in md.lower()
    assert ":---" in md


def test_timeline_dates_present(timeline_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_timeline
    md = render_timeline(timeline_data)
    assert "1991" in md
    assert "2008" in md
    assert "2020" in md


def test_timeline_detailed_bullets(timeline_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_timeline
    md = render_timeline(timeline_data)
    assert "Detailed Timeline" in md
    assert "**1991**" in md


# ---------------------------------------------------------------------------
# render_mindmap
# ---------------------------------------------------------------------------

def test_mindmap_central_topic(mindmap_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_mindmap
    md = render_mindmap(mindmap_data)
    assert "# Python" in md


def test_mindmap_branches_as_h2(mindmap_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_mindmap
    md = render_mindmap(mindmap_data)
    assert "## Data Types" in md
    assert "## Control Flow" in md


def test_mindmap_children_as_bullets(mindmap_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_mindmap
    md = render_mindmap(mindmap_data)
    assert "- list" in md
    assert "- if" in md


# ---------------------------------------------------------------------------
# render_research_review
# ---------------------------------------------------------------------------

def test_research_review_title(research_review_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_research_review
    md = render_research_review(research_review_data)
    assert "# Research Review: Training-Free GRPO" in md


def test_research_review_bluf(research_review_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_research_review
    md = render_research_review(research_review_data)
    assert "> **BLUF:**" in md
    assert "Skeptical" in md


def test_research_review_resource_link(research_review_data) -> None:
    from open_notebook.artifacts.renderers.markdown import render_research_review
    md = render_research_review(research_review_data)
    assert "[arXiv](https://arxiv.org/abs/1234)" in md


# ---------------------------------------------------------------------------
# write helper
# ---------------------------------------------------------------------------

def test_write_creates_file(tmp_path: Path) -> None:
    from open_notebook.artifacts.renderers.markdown import write
    out = tmp_path / "sub" / "out.md"
    result = write(out, "# Hello\n")
    assert result.exists()
    assert result.read_text() == "# Hello\n"
