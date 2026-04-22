"""Unit tests for FAQGenerator — schema, registry, and model-type checks.

No real LLM calls. Tests verify:
1. FAQSchema / FAQItemSchema have required fields.
2. FAQGenerator is registered in ARTIFACT_TYPES.
3. FAQGenerator.default_model_type is set.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_faq_schema_required_fields() -> None:
    """FAQSchema must expose title and items."""
    from open_notebook.artifacts.generators.faq import FAQSchema

    schema_fields = set(FAQSchema.model_fields.keys())
    required = {"title", "items"}
    missing = required - schema_fields
    assert not missing, (
        f"FAQSchema is missing required fields: {missing}. Present: {schema_fields}"
    )


def test_faq_item_schema_required_fields() -> None:
    """FAQItemSchema must have question and answer fields."""
    from open_notebook.artifacts.generators.faq import FAQItemSchema

    item_fields = set(FAQItemSchema.model_fields.keys())
    required = {"question", "answer"}
    missing = required - item_fields
    assert not missing, (
        f"FAQItemSchema is missing required fields: {missing}. Present: {item_fields}"
    )


def test_faq_schema_instantiation() -> None:
    """FAQSchema must be constructible with valid nested data."""
    from open_notebook.artifacts.generators.faq import FAQItemSchema, FAQSchema

    obj = FAQSchema(
        title="FAQ: Retrieval-Augmented Generation",
        items=[
            FAQItemSchema(question="What is RAG?", answer="A technique that combines retrieval with generation."),
            FAQItemSchema(question="Why use RAG?", answer="To ground LLM outputs in retrieved documents."),
        ],
    )
    assert obj.title == "FAQ: Retrieval-Augmented Generation"
    assert len(obj.items) == 2
    dumped = obj.model_dump()
    assert dumped["items"][0]["question"] == "What is RAG?"


def test_faq_generator_in_registry() -> None:
    """FAQGenerator must be registered in ARTIFACT_TYPES."""
    from open_notebook.artifacts.registry import ARTIFACT_TYPES

    assert "faq" in ARTIFACT_TYPES, (
        f"'faq' not found in ARTIFACT_TYPES. Registered: {sorted(ARTIFACT_TYPES.keys())}"
    )


def test_faq_generator_default_model_type() -> None:
    """FAQGenerator.default_model_type must be a non-empty string."""
    from open_notebook.artifacts.generators.faq import FAQGenerator

    assert FAQGenerator.default_model_type, (
        "FAQGenerator.default_model_type must be set."
    )
    assert isinstance(FAQGenerator.default_model_type, str)


def test_faq_generator_uses_chunked_generate() -> None:
    """FAQGenerator.generate must call chunked_generate."""
    import inspect

    from open_notebook.artifacts.generators.faq import FAQGenerator

    source = inspect.getsource(FAQGenerator.generate)
    assert "chunked_generate" in source, (
        "FAQGenerator.generate must call self.chunked_generate()."
    )
    assert "generate_json" not in source, (
        "FAQGenerator must not use generate_json (legacy)."
    )
