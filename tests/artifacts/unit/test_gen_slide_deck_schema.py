"""Unit tests for SlideDeckGenerator — schema, registry, and config contract."""
from __future__ import annotations
import pytest
from open_notebook.artifacts.generators.slide_deck import (
    SlideDeckGenerator, SlideDeckSchema, SlideSchema,
)
from open_notebook.artifacts.registry import ARTIFACT_TYPES

pytestmark = pytest.mark.unit


class TestSlideDeckSchema:
    def test_schema_has_title(self):
        assert "title" in SlideDeckSchema.model_fields

    def test_schema_has_slides(self):
        assert "slides" in SlideDeckSchema.model_fields

    def test_slide_schema_has_title_bullets_notes(self):
        fields = SlideSchema.model_fields
        assert "title" in fields
        assert "bullets" in fields
        assert "notes" in fields

    def test_schema_validates_correctly(self):
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
        deck = SlideDeckSchema(
            title="Round Trip",
            slides=[SlideSchema(title="S1", bullets=["B1"])],
        )
        restored = SlideDeckSchema.model_validate(deck.model_dump())
        assert restored.title == "Round Trip"
        assert restored.slides[0].title == "S1"


class TestSlideDeckGeneratorRegistry:
    def test_generator_registered(self):
        assert "slide_deck" in ARTIFACT_TYPES

    def test_registered_class_is_slide_deck_generator(self):
        assert ARTIFACT_TYPES["slide_deck"] is SlideDeckGenerator


class TestSlideDeckGeneratorConfig:
    def test_default_model_type_is_set(self):
        assert SlideDeckGenerator.default_model_type
        assert isinstance(SlideDeckGenerator.default_model_type, str)

    def test_artifact_type_is_slide_deck(self):
        assert SlideDeckGenerator.artifact_type == "slide_deck"

    def test_description_is_non_empty(self):
        assert SlideDeckGenerator.description
