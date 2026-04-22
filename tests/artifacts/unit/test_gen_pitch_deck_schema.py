"""Unit tests for PitchDeckGenerator — schema, registry, and config contract.

No real LLM calls. All assertions are structural / contract-level.
"""
from __future__ import annotations

import pytest

from open_notebook.artifacts.generators.pitch_deck import (
    PitchDeckGenerator,
    PitchDeckSchema,
    PitchSlideSchema,
)
from open_notebook.artifacts.registry import ARTIFACT_TYPES


pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# 1. Schema has required fields
# ---------------------------------------------------------------------------

class TestPitchDeckSchema:
    def test_schema_has_title(self):
        assert "title" in PitchDeckSchema.model_fields

    def test_schema_has_tagline(self):
        assert "tagline" in PitchDeckSchema.model_fields

    def test_schema_has_slides(self):
        assert "slides" in PitchDeckSchema.model_fields

    def test_pitch_slide_schema_fields(self):
        fields = PitchSlideSchema.model_fields
        assert "title" in fields
        assert "bullets" in fields
        assert "notes" in fields

    def test_schema_validates_vc_deck(self):
        """Validate a minimal VC pitch deck."""
        deck = PitchDeckSchema(
            title="AcmeCo",
            tagline="AI that writes itself",
            slides=[
                PitchSlideSchema(title="Problem", bullets=["Pain point A", "Pain point B"]),
                PitchSlideSchema(title="Solution", bullets=["Our fix"], notes="Expand here"),
                PitchSlideSchema(title="Ask", bullets=["$5M seed"]),
            ],
        )
        assert deck.tagline == "AI that writes itself"
        assert len(deck.slides) == 3

    def test_schema_round_trips(self):
        deck = PitchDeckSchema(
            title="StartupX",
            tagline="tagline",
            slides=[PitchSlideSchema(title="Cover", bullets=["Hi"])],
        )
        restored = PitchDeckSchema.model_validate(deck.model_dump())
        assert restored.title == "StartupX"
        assert restored.slides[0].title == "Cover"


# ---------------------------------------------------------------------------
# 2. Generator class is in ARTIFACT_TYPES
# ---------------------------------------------------------------------------

class TestPitchDeckGeneratorRegistry:
    def test_generator_registered(self):
        assert "pitch_deck" in ARTIFACT_TYPES

    def test_registered_class_is_pitch_deck_generator(self):
        assert ARTIFACT_TYPES["pitch_deck"] is PitchDeckGenerator


# ---------------------------------------------------------------------------
# 3. Generator's default_model_type is set
# ---------------------------------------------------------------------------

class TestPitchDeckGeneratorConfig:
    def test_default_model_type_is_set(self):
        assert PitchDeckGenerator.default_model_type
        assert isinstance(PitchDeckGenerator.default_model_type, str)

    def test_artifact_type_is_pitch_deck(self):
        assert PitchDeckGenerator.artifact_type == "pitch_deck"

    def test_description_is_non_empty(self):
        assert PitchDeckGenerator.description
