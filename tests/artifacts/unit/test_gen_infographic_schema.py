"""Unit tests for InfographicGenerator — schema, registry, and config contract."""
from __future__ import annotations
import pytest
from open_notebook.artifacts.generators.infographic import (
    InfographicGenerator, InfographicSchema, InfographicSectionSchema, InfographicStatSchema,
)
from open_notebook.artifacts.registry import ARTIFACT_TYPES

pytestmark = pytest.mark.unit


class TestInfographicSchema:
    def test_schema_has_title(self):
        assert "title" in InfographicSchema.model_fields

    def test_schema_has_sections(self):
        assert "sections" in InfographicSchema.model_fields

    def test_schema_has_stats(self):
        assert "stats" in InfographicSchema.model_fields

    def test_schema_has_color_theme(self):
        assert "color_theme" in InfographicSchema.model_fields

    def test_section_schema_fields(self):
        fields = InfographicSectionSchema.model_fields
        assert "heading" in fields
        assert "text" in fields

    def test_stat_schema_fields(self):
        fields = InfographicStatSchema.model_fields
        assert "value" in fields
        assert "label" in fields

    def test_color_theme_must_be_literal(self):
        ig = InfographicSchema(
            title="Test",
            sections=[InfographicSectionSchema(heading="H", text="T")],
            stats=[InfographicStatSchema(value="50%", label="adoption")],
            color_theme="green",
        )
        assert ig.color_theme == "green"

    def test_schema_rejects_invalid_color_theme(self):
        with pytest.raises(Exception):
            InfographicSchema(
                title="Bad", sections=[], stats=[],
                color_theme="purple",  # type: ignore
            )

    def test_schema_validates_complete_infographic(self):
        ig = InfographicSchema(
            title="AI Adoption in 2025",
            subtitle="Key stats and trends",
            sections=[
                InfographicSectionSchema(heading="Overview", text="AI is everywhere."),
                InfographicSectionSchema(heading="Challenges", text="Cost and talent gaps."),
            ],
            stats=[
                InfographicStatSchema(value="82%", label="enterprises using AI"),
                InfographicStatSchema(value="3x", label="productivity gain"),
            ],
            color_theme="blue",
        )
        assert ig.title == "AI Adoption in 2025"
        assert len(ig.sections) == 2
        assert len(ig.stats) == 2

    def test_schema_round_trips(self):
        ig = InfographicSchema(
            title="Round Trip",
            sections=[InfographicSectionSchema(heading="S", text="t")],
            stats=[InfographicStatSchema(value="1", label="one")],
        )
        restored = InfographicSchema.model_validate(ig.model_dump())
        assert restored.title == "Round Trip"
        assert restored.color_theme == "blue"  # default


class TestInfographicGeneratorRegistry:
    def test_generator_registered(self):
        assert "infographic" in ARTIFACT_TYPES

    def test_registered_class_is_infographic_generator(self):
        assert ARTIFACT_TYPES["infographic"] is InfographicGenerator


class TestInfographicGeneratorConfig:
    def test_default_model_type_is_set(self):
        assert InfographicGenerator.default_model_type
        assert isinstance(InfographicGenerator.default_model_type, str)

    def test_artifact_type_is_infographic(self):
        assert InfographicGenerator.artifact_type == "infographic"

    def test_description_is_non_empty(self):
        assert InfographicGenerator.description
