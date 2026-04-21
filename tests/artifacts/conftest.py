"""Shared fixtures for artifact-generator tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from open_notebook.artifacts import ArtifactSource
from open_notebook.artifacts.llm import ArtifactLLM, make_echo_generator


SAMPLE_TEXT = """Title: Training-Free GRPO
Authors: Yuzheng Cai, Siqi Cai.
Affiliations: Tencent Youtu Lab, Fudan University, Xiamen University.

The paper proposes Training-Free GRPO, doing GRPO-style RL optimization
through prompt engineering instead of parameter updates. The method
generates multiple rollouts per query, uses the LLM to introspect on
successes and failures, and extracts natural language experiences.

On AIME 2024 they improve DeepSeek-V3.1-Terminus from 80.0 to 82.7
with just 100 training samples. They claim 100x less data and 500x
lower cost than fine-tuning 32B models.

Notable limitation: the authors never compare their method to
traditional GRPO on the same base model. Published October 2025 on arXiv.
"""


@pytest.fixture
def sample_source() -> ArtifactSource:
    return ArtifactSource(title="Training-Free GRPO", content=SAMPLE_TEXT)


@pytest.fixture
def sample_sources(sample_source) -> list[ArtifactSource]:
    return [sample_source]


@pytest.fixture
def output_dir(tmp_path: Path) -> str:
    return str(tmp_path / "artifacts")


@pytest.fixture
def canned_llm():
    """Return an ``ArtifactLLM`` that emits a structured fixture per artifact."""

    def payload_for(prompt: str):
        prompt_lower = prompt.lower()
        if "executive briefing" in prompt_lower or "bluf" in prompt_lower and "key_points" in prompt_lower:
            return {
                "title": "Test Briefing",
                "audience": "Executive",
                "bluf": "A fixture BLUF.",
                "key_points": ["Point A", "Point B"],
                "supporting_details": ["Detail A"],
                "action_items": ["Act A"],
                "keywords": ["kw1"],
            }
        if "study guide" in prompt_lower:
            return {
                "title": "Test Study Guide",
                "overview": "overview",
                "learning_objectives": ["Understand X"],
                "key_concepts": ["K1", "K2"],
                "glossary": [{"term": "T", "definition": "D"}],
                "discussion_questions": ["Q1?"],
                "further_reading": [],
            }
        if "faq" in prompt_lower:
            return {
                "title": "Test FAQ",
                "items": [{"question": "Q?", "answer": "A."}],
            }
        if "research review" in prompt_lower:
            return {
                "title": "Test Review",
                "bluf": "Skeptical take.",
                "notable_authors": ["Cai"],
                "affiliations": ["Tencent"],
                "short_take": "short take",
                "why_we_care": {"direct_techniques": ["tech"]},
                "limitations": ["limit"],
                "potential_applications": ["use"],
                "resources": [{"label": "arXiv", "url": "https://arxiv.org/"}],
            }
        if "flashcard" in prompt_lower:
            return {
                "title": "Test Cards",
                "cards": [
                    {"front": "F1", "back": "B1", "tags": ["a"]},
                    {"front": "F2", "back": "B2", "tags": ["b"]},
                ],
            }
        if "multiple-choice" in prompt_lower or "quiz" in prompt_lower:
            return {
                "title": "Test Quiz",
                "questions": [
                    {
                        "question": "Q1?",
                        "options": ["A", "B", "C", "D"],
                        "answer_index": 1,
                        "explanation": "Because B",
                    }
                ],
            }
        if "mind map" in prompt_lower:
            return {
                "central_topic": "Central",
                "branches": [
                    {"label": "B1", "children": ["c1", "c2"]},
                    {"label": "B2", "children": ["c3"]},
                ],
            }
        if "timeline" in prompt_lower:
            return {
                "title": "Test Timeline",
                "events": [
                    {"date": "2020", "event": "Alpha"},
                    {"date": "2024", "event": "Beta"},
                ],
            }
        if "infographic" in prompt_lower:
            return {
                "title": "Test Infographic",
                "subtitle": "Subtitle",
                "sections": [
                    {"heading": "Sec 1", "text": "Details 1"},
                    {"heading": "Sec 2", "text": "Details 2"},
                ],
                "stats": [{"value": "82%", "label": "success"}],
                "color_theme": "blue",
            }
        if "pitch deck" in prompt_lower:
            return {
                "title": "Pitch",
                "tagline": "Tagline",
                "slides": [
                    {"title": "Cover", "bullets": ["Line"], "notes": "n"},
                    {"title": "Problem", "bullets": ["P1"], "notes": "n"},
                ],
            }
        if "slide deck" in prompt_lower or "informational slide" in prompt_lower:
            return {
                "title": "Deck",
                "subtitle": "Sub",
                "slides": [
                    {"title": "Intro", "bullets": ["Hello"], "notes": ""},
                    {"title": "Main", "bullets": ["B1", "B2"], "notes": "notes"},
                ],
            }
        if "figure" in prompt_lower:
            return {
                "title": "Figure",
                "chart_type": "bar",
                "x_label": "x",
                "y_label": "y",
                "series": [
                    {
                        "name": "s1",
                        "data": [{"x": "A", "y": 1.0}, {"x": "B", "y": 2.0}],
                    }
                ],
                "caption": "caption",
            }
        return {"title": "Generic", "summary": "summary"}

    return ArtifactLLM(text_generator=make_echo_generator(payload_for))
