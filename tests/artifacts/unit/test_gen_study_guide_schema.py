"""Unit tests for StudyGuideGenerator — schema, registry, and model-type checks.

No real LLM calls. Tests verify:
1. StudyGuideSchema / GlossaryTermSchema have required fields.
2. StudyGuideGenerator is registered in ARTIFACT_TYPES.
3. StudyGuideGenerator.default_model_type is set.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_study_guide_schema_required_fields() -> None:
    """StudyGuideSchema must expose all plan-required fields."""
    from open_notebook.artifacts.generators.study_guide import StudyGuideSchema

    schema_fields = set(StudyGuideSchema.model_fields.keys())
    required = {
        "title",
        "overview",
        "learning_objectives",
        "key_concepts",
        "glossary",
        "discussion_questions",
    }
    missing = required - schema_fields
    assert not missing, (
        f"StudyGuideSchema is missing required fields: {missing}. Present: {schema_fields}"
    )


def test_glossary_term_schema_required_fields() -> None:
    """GlossaryTermSchema must have term and definition."""
    from open_notebook.artifacts.generators.study_guide import GlossaryTermSchema

    g_fields = set(GlossaryTermSchema.model_fields.keys())
    required = {"term", "definition"}
    missing = required - g_fields
    assert not missing, (
        f"GlossaryTermSchema is missing required fields: {missing}. Present: {g_fields}"
    )


def test_study_guide_schema_instantiation() -> None:
    """StudyGuideSchema must be constructible with valid nested data."""
    from open_notebook.artifacts.generators.study_guide import (
        GlossaryTermSchema,
        StudyGuideSchema,
    )

    obj = StudyGuideSchema(
        title="Study Guide: Attention in Neural Networks",
        overview="This guide covers the attention mechanism and its variants.",
        learning_objectives=[
            "Explain how scaled dot-product attention works.",
            "Apply multi-head attention to a classification task.",
        ],
        key_concepts=[
            "Attention weights are derived from query-key dot products.",
            "Multi-head attention runs several attention operations in parallel.",
        ],
        glossary=[
            GlossaryTermSchema(
                term="Query",
                definition="A vector derived from the current token used to compute attention scores.",
            ),
            GlossaryTermSchema(
                term="Key",
                definition="A vector against which query similarity is measured.",
            ),
        ],
        discussion_questions=[
            "How does positional encoding interact with attention?",
            "What are the computational costs of full self-attention?",
        ],
        further_reading=["The Annotated Transformer (Harvard NLP)"],
    )
    assert obj.title == "Study Guide: Attention in Neural Networks"
    assert len(obj.glossary) == 2
    dumped = obj.model_dump()
    assert dumped["glossary"][0]["term"] == "Query"


def test_study_guide_generator_in_registry() -> None:
    """StudyGuideGenerator must be registered in ARTIFACT_TYPES."""
    from open_notebook.artifacts.registry import ARTIFACT_TYPES

    assert "study_guide" in ARTIFACT_TYPES, (
        f"'study_guide' not in ARTIFACT_TYPES. Registered: {sorted(ARTIFACT_TYPES.keys())}"
    )


def test_study_guide_generator_default_model_type() -> None:
    """StudyGuideGenerator.default_model_type must be a non-empty string."""
    from open_notebook.artifacts.generators.study_guide import StudyGuideGenerator

    assert StudyGuideGenerator.default_model_type, (
        "StudyGuideGenerator.default_model_type must be set."
    )
    assert isinstance(StudyGuideGenerator.default_model_type, str)


def test_study_guide_generator_uses_chunked_generate() -> None:
    """StudyGuideGenerator.generate must call chunked_generate."""
    import inspect

    from open_notebook.artifacts.generators.study_guide import StudyGuideGenerator

    source = inspect.getsource(StudyGuideGenerator.generate)
    assert "chunked_generate" in source, (
        "StudyGuideGenerator.generate must call self.chunked_generate()."
    )
    assert "generate_json" not in source, (
        "StudyGuideGenerator must not use generate_json (legacy)."
    )
