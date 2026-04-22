"""Unit tests for TimelineGenerator — schema, registry, and model-type checks.

No real LLM calls. Tests verify:
1. TimelineSchema / TimelineEventSchema have required fields.
2. TimelineGenerator is registered in ARTIFACT_TYPES.
3. TimelineGenerator.default_model_type is set.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_timeline_schema_required_fields() -> None:
    """TimelineSchema must expose title and events."""
    from open_notebook.artifacts.generators.timeline import TimelineSchema

    schema_fields = set(TimelineSchema.model_fields.keys())
    required = {"title", "events"}
    missing = required - schema_fields
    assert not missing, (
        f"TimelineSchema is missing required fields: {missing}. Present: {schema_fields}"
    )


def test_timeline_event_schema_required_fields() -> None:
    """TimelineEventSchema must have date, event, and significance."""
    from open_notebook.artifacts.generators.timeline import TimelineEventSchema

    event_fields = set(TimelineEventSchema.model_fields.keys())
    required = {"date", "event", "significance"}
    missing = required - event_fields
    assert not missing, (
        f"TimelineEventSchema is missing required fields: {missing}. Present: {event_fields}"
    )


def test_timeline_schema_instantiation() -> None:
    """TimelineSchema must be constructible with valid nested data."""
    from open_notebook.artifacts.generators.timeline import TimelineEventSchema, TimelineSchema

    obj = TimelineSchema(
        title="Timeline: Transformer Architecture",
        events=[
            TimelineEventSchema(
                date="2017",
                event="Vaswani et al. publish 'Attention Is All You Need'.",
                significance="Introduced the transformer architecture, replacing RNNs for seq2seq tasks.",
            ),
            TimelineEventSchema(
                date="2018",
                event="BERT is released by Google.",
                significance="Demonstrated that bidirectional transformers achieve SOTA on NLP benchmarks.",
            ),
            TimelineEventSchema(
                date="2020",
                event="GPT-3 is released by OpenAI.",
                significance="Showed that scaling transformers produces emergent few-shot capabilities.",
            ),
        ],
    )
    assert obj.title == "Timeline: Transformer Architecture"
    assert len(obj.events) == 3
    dumped = obj.model_dump()
    assert dumped["events"][0]["date"] == "2017"
    assert "Attention" in dumped["events"][0]["event"]


def test_timeline_generator_in_registry() -> None:
    """TimelineGenerator must be registered in ARTIFACT_TYPES."""
    from open_notebook.artifacts.registry import ARTIFACT_TYPES

    assert "timeline" in ARTIFACT_TYPES, (
        f"'timeline' not in ARTIFACT_TYPES. Registered: {sorted(ARTIFACT_TYPES.keys())}"
    )


def test_timeline_generator_default_model_type() -> None:
    """TimelineGenerator.default_model_type must be a non-empty string."""
    from open_notebook.artifacts.generators.timeline import TimelineGenerator

    assert TimelineGenerator.default_model_type, (
        "TimelineGenerator.default_model_type must be set."
    )
    assert isinstance(TimelineGenerator.default_model_type, str)


def test_timeline_generator_uses_chunked_generate() -> None:
    """TimelineGenerator.generate must call chunked_generate."""
    import inspect

    from open_notebook.artifacts.generators.timeline import TimelineGenerator

    source = inspect.getsource(TimelineGenerator.generate)
    assert "chunked_generate" in source, (
        "TimelineGenerator.generate must call self.chunked_generate()."
    )
    assert "generate_json" not in source, (
        "TimelineGenerator must not use generate_json (legacy)."
    )
