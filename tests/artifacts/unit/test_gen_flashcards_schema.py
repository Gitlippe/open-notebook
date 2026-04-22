"""Unit tests for FlashcardsGenerator — schema, registry, and model-type checks.

No real LLM calls. Tests verify:
1. FlashcardsSchema / FlashcardSchema have required fields.
2. FlashcardsGenerator is registered in ARTIFACT_TYPES.
3. FlashcardsGenerator.default_model_type is set.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_flashcards_schema_required_fields() -> None:
    """FlashcardsSchema must expose title and cards."""
    from open_notebook.artifacts.generators.flashcards import FlashcardsSchema

    schema_fields = set(FlashcardsSchema.model_fields.keys())
    required = {"title", "cards"}
    missing = required - schema_fields
    assert not missing, (
        f"FlashcardsSchema is missing required fields: {missing}. Present: {schema_fields}"
    )


def test_flashcard_schema_required_fields() -> None:
    """FlashcardSchema must have front and back fields."""
    from open_notebook.artifacts.generators.flashcards import FlashcardSchema

    card_fields = set(FlashcardSchema.model_fields.keys())
    required = {"front", "back"}
    missing = required - card_fields
    assert not missing, (
        f"FlashcardSchema is missing required fields: {missing}. Present: {card_fields}"
    )


def test_flashcard_schema_tags_optional() -> None:
    """FlashcardSchema.tags should have a default (not required)."""
    from open_notebook.artifacts.generators.flashcards import FlashcardSchema

    # Should not raise even without tags
    card = FlashcardSchema(front="What is attention?", back="A mechanism that weights token relevance.")
    assert card.tags == []


def test_flashcards_schema_instantiation() -> None:
    """FlashcardsSchema must be constructible with valid nested data."""
    from open_notebook.artifacts.generators.flashcards import FlashcardSchema, FlashcardsSchema

    obj = FlashcardsSchema(
        title="Flashcards: Transformers",
        cards=[
            FlashcardSchema(
                front="What does the 'attention' mechanism compute?",
                back="A weighted sum of value vectors, where weights derive from query-key dot products.",
                tags=["transformers", "attention"],
            ),
            FlashcardSchema(
                front="What is positional encoding?",
                back="A signal added to token embeddings to convey sequence order.",
                tags=["transformers", "encoding"],
            ),
        ],
    )
    assert len(obj.cards) == 2
    dumped = obj.model_dump()
    assert dumped["cards"][0]["front"] == "What does the 'attention' mechanism compute?"


def test_flashcards_generator_in_registry() -> None:
    """FlashcardsGenerator must be registered in ARTIFACT_TYPES."""
    from open_notebook.artifacts.registry import ARTIFACT_TYPES

    assert "flashcards" in ARTIFACT_TYPES, (
        f"'flashcards' not in ARTIFACT_TYPES. Registered: {sorted(ARTIFACT_TYPES.keys())}"
    )


def test_flashcards_generator_default_model_type() -> None:
    """FlashcardsGenerator.default_model_type must be a non-empty string."""
    from open_notebook.artifacts.generators.flashcards import FlashcardsGenerator

    assert FlashcardsGenerator.default_model_type, (
        "FlashcardsGenerator.default_model_type must be set."
    )
    assert isinstance(FlashcardsGenerator.default_model_type, str)


def test_flashcards_generator_uses_chunked_generate() -> None:
    """FlashcardsGenerator.generate must call chunked_generate."""
    import inspect

    from open_notebook.artifacts.generators.flashcards import FlashcardsGenerator

    source = inspect.getsource(FlashcardsGenerator.generate)
    assert "chunked_generate" in source, (
        "FlashcardsGenerator.generate must call self.chunked_generate()."
    )
    assert "generate_json" not in source, (
        "FlashcardsGenerator must not use generate_json (legacy)."
    )
