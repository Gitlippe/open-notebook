"""Unit tests for PaperFigureGenerator — schema, registry, and config contract.

No real LLM calls. All assertions are structural / contract-level.
"""
from __future__ import annotations

import pytest

from open_notebook.artifacts.generators.paper_figure import (
    DataPointSchema,
    PaperFigureGenerator,
    PaperFigureSchema,
    SeriesSchema,
)
from open_notebook.artifacts.registry import ARTIFACT_TYPES


pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# 1. Schema has required fields
# ---------------------------------------------------------------------------

class TestPaperFigureSchema:
    def test_schema_has_title(self):
        assert "title" in PaperFigureSchema.model_fields

    def test_schema_has_chart_type(self):
        assert "chart_type" in PaperFigureSchema.model_fields

    def test_schema_has_series(self):
        assert "series" in PaperFigureSchema.model_fields

    def test_schema_has_caption(self):
        assert "caption" in PaperFigureSchema.model_fields

    def test_schema_has_axis_labels(self):
        assert "x_label" in PaperFigureSchema.model_fields
        assert "y_label" in PaperFigureSchema.model_fields

    def test_series_schema_fields(self):
        assert "name" in SeriesSchema.model_fields
        assert "data" in SeriesSchema.model_fields

    def test_data_point_schema_fields(self):
        assert "x" in DataPointSchema.model_fields
        assert "y" in DataPointSchema.model_fields

    def test_chart_type_must_be_literal(self):
        """chart_type must be bar, line, or scatter."""
        fig = PaperFigureSchema(
            title="Figure 1",
            chart_type="bar",
            x_label="Category",
            y_label="Value",
            series=[SeriesSchema(name="Series A", data=[DataPointSchema(x="A", y=1.0)])],
            caption="A test figure.",
        )
        assert fig.chart_type == "bar"

    def test_schema_rejects_invalid_chart_type(self):
        with pytest.raises(Exception):
            PaperFigureSchema(
                title="Bad",
                chart_type="pie",  # type: ignore
                x_label="x",
                y_label="y",
                series=[],
                caption="nope",
            )

    def test_schema_validates_scatter(self):
        fig = PaperFigureSchema(
            title="Scatter",
            chart_type="scatter",
            x_label="X",
            y_label="Y",
            series=[
                SeriesSchema(
                    name="data",
                    data=[DataPointSchema(x=1.0, y=2.0), DataPointSchema(x=3.0, y=4.0)],
                )
            ],
            caption="Scatter plot.",
        )
        assert len(fig.series[0].data) == 2

    def test_schema_round_trips(self):
        fig = PaperFigureSchema(
            title="Line Chart",
            chart_type="line",
            x_label="Year",
            y_label="Revenue",
            series=[SeriesSchema(name="Rev", data=[DataPointSchema(x="2020", y=100.0)])],
            caption="Revenue over time.",
        )
        restored = PaperFigureSchema.model_validate(fig.model_dump())
        assert restored.chart_type == "line"
        assert restored.series[0].name == "Rev"


# ---------------------------------------------------------------------------
# 2. Generator class is in ARTIFACT_TYPES
# ---------------------------------------------------------------------------

class TestPaperFigureGeneratorRegistry:
    def test_generator_registered(self):
        assert "paper_figure" in ARTIFACT_TYPES

    def test_registered_class_is_paper_figure_generator(self):
        assert ARTIFACT_TYPES["paper_figure"] is PaperFigureGenerator


# ---------------------------------------------------------------------------
# 3. Generator's default_model_type is set
# ---------------------------------------------------------------------------

class TestPaperFigureGeneratorConfig:
    def test_default_model_type_is_set(self):
        assert PaperFigureGenerator.default_model_type
        assert isinstance(PaperFigureGenerator.default_model_type, str)

    def test_artifact_type_is_paper_figure(self):
        assert PaperFigureGenerator.artifact_type == "paper_figure"

    def test_description_is_non_empty(self):
        assert PaperFigureGenerator.description
