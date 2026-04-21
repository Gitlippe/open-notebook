"""Tests for the ArtifactLLM adapter."""
from __future__ import annotations

import pytest

from open_notebook.artifacts.llm import (
    ArtifactLLM,
    _parse_json_loose,
    combine_prompts,
    make_echo_generator,
    make_static_generator,
)


def test_parse_json_loose_direct():
    assert _parse_json_loose('{"a": 1}') == {"a": 1}


def test_parse_json_loose_fenced():
    text = "some junk\n```json\n{\"x\": 2}\n```\n"
    assert _parse_json_loose(text) == {"x": 2}


def test_parse_json_loose_with_prose():
    text = 'Preamble here. {"a": 1, "b": [1,2]} trailing text'
    assert _parse_json_loose(text) == {"a": 1, "b": [1, 2]}


def test_parse_json_loose_rejects_nonjson():
    assert _parse_json_loose("") is None
    assert _parse_json_loose("definitely not json") is None


def test_combine_prompts_structure():
    combined = combine_prompts("instructions here", "body here")
    assert combined.startswith("instructions here")
    assert "# INPUT" in combined
    assert combined.endswith("body here")


@pytest.mark.asyncio
async def test_llm_prefers_injected_generator():
    llm = ArtifactLLM(
        text_generator=make_static_generator({"foo": "bar"})
    )
    result = await llm.generate_json("prompt")
    assert result == {"foo": "bar"}


@pytest.mark.asyncio
async def test_llm_falls_back_to_heuristic_on_bad_output():
    async def bad_generator(_prompt):
        return "not json at all"

    llm = ArtifactLLM(text_generator=bad_generator)
    result = await llm.generate_json("prompt\n\n# INPUT\n\ntext", artifact_type="briefing")
    assert "bluf" in result


@pytest.mark.asyncio
async def test_make_echo_generator_roundtrip():
    gen = make_echo_generator(lambda _p: {"k": "v"})
    result = await gen("hello")
    assert result == '{"k": "v"}'
