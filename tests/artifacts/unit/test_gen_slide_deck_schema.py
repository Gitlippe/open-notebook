"""Unit tests for SlideDeckGenerator — schema, registry, and config contract.

No real LLM calls. All assertions are structural / contract-level.
"""
from __future__ import annotations

import pytest

from open_notebook.artifacts.generators.slide_deck import (
    SlideDeckGenerator,
    SlideDeckSchema,
    SlideSchema,
)
from open_notebook.artifacts.registry import ARTIFACT_TYPES


pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# 1. Schema has required fields
# ---------------------------------------------------------------------------

class TestSlideDeckSchema:
    def test_schema_has_title(self):
        """SlideDeckSchema requires a title field."""
        assert "title" in SlideDeckSchema.model_fields

    def test_schema_has_slides(self):
        """SlideDeckSchema requires a slides list."""
        assert "slides" in SlideDeckSchema.model_fields

    def test_slide_schema_has_title_bullets_notes(self):
        """SlideSchema has title, bullets, and optional notes."""
        fields = SlideSchema.model_fields
        assert "title" in fields
        assert "bullets" in fields
        assert "notes" in fields

    def test_schema_validates_correctly(self):
        """SlideDeckSchema validates a well-formed deck."""
        deck = SlideDeckSchema(
            title="Test Deck",
            subtitle="A subtitle",
            slides=[
                SlideSchema(title="Intro", bullets=["Hello", "World"], notes="Notes"),
                SlideSchema(title="Conclusion", bullets=["Summary"]),
            ],
        )
        assert deck.title == "Test Deck"
        assert len(deck.slides) == 2
        assert deck.slides[0].notes == "Notes"
        assert deck.slides[1].notes is None

    def test_schema_round_trips_via_model_dump(self):
        """model_dump() output can be validated back into SlideDeckSchema."""
        deck = SlideDeckSchema(
            title="Round Trip",
            slides=[SlideSchema(title="S1", bullets=["B1"])],
        )
        dumped = deck.model_dump()
        restored = SlideDeckSchema.model_validate(dumped)
        assert restored.title == "Round Trip"
        assert restored.slides[0].title == "S1"


# ---------------------------------------------------------------------------
# 2. Generator class is in ARTIFACT_TYPES
# ---------------------------------------------------------------------------

class TestSlideDeckGeneratorRegistry:
    def test_generator_registered(self):
        """SlideDeckGenerator must appear in ARTIFACT_TYPES."""
        assert "slide_deck" in ARTIFACT_TYPES

    def test_registered_class_is_slide_deck_generator(self):
        """The registered class is exactly SlideDeckGenerator."""
        assert ARTIFACT_TYPES["slide_deck"] is SlideDeckGenerator


# ---------------------------------------------------------------------------
# 3. Generator's default_model_type is set
# ---------------------------------------------------------------------------

class TestSlideDeckGeneratorConfig:
    def test_default_model_type_is_set(self):
        """SlideDeckGenerator.default_model_type must be non-empty."""
        assert SlideDeckGenerator.default_model_type
        assert isinstance(SlideDeckGenerator.default_model_type, str)

    def test_artifact_type_is_slide_deck(self):
        assert SlideDeckGenerator.artifact_type == "slide_deck"

    def test_description_is_non_empty(self):
        assert SlideDeckGenerator.description
