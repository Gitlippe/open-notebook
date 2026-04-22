"""Integration tests for the chart renderer.

Marker: ``integration`` (no real LLM needed — hand-constructed schemas).

These tests:
1. Render a bar, line, and scatter chart and verify PNG dimensions >= 800x600.
2. Assert that an unsupported chart type raises ``ValueError`` (no silent fallback).
3. Verify the returned result contains both a file path and a base64 string.
4. Verify the rendered PNG is valid via PIL.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from open_notebook.artifacts.generators.paper_figure import (
    DataPointSchema,
    PaperFigureSchema,
    SeriesSchema,
)
from open_notebook.artifacts.renderers.chart_renderer import render_paper_figure

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_schema(
    chart_type: str,
    n_points: int = 5,
    n_series: int = 2,
) -> PaperFigureSchema:
    series = []
    for s in range(n_series):
        pts = []
        for i in range(n_points):
            if chart_type == "bar":
                pts.append(DataPointSchema(x=f"Cat{i}", y=float(s * 10 + i)))
            else:
                pts.append(DataPointSchema(x=float(i), y=float(s * 10 + i)))
        series.append(SeriesSchema(name=f"Series {s+1}", data=pts))

    return PaperFigureSchema(
        title=f"Test {chart_type.capitalize()} Chart",
        chart_type=chart_type,  # type: ignore[arg-type]
        x_label="X Axis",
        y_label="Y Axis",
        series=series,
        caption=f"Automated test for {chart_type} chart type.",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBarChart:
    def test_bar_chart_renders_valid_png(self, tmp_path: Path) -> None:
        schema = _make_schema("bar")
        result = render_paper_figure(schema.model_dump(), tmp_path / "bar.png")

        assert result.path.exists(), "PNG file was not created."
        img = Image.open(result.path)
        img.verify()  # raises if not valid PNG

    def test_bar_chart_dimensions(self, tmp_path: Path) -> None:
        """Rendered PNG must be at least 800×600 px."""
        schema = _make_schema("bar")
        result = render_paper_figure(schema.model_dump(), tmp_path / "bar_size.png")

        img = Image.open(result.path)
        w, h = img.size
        assert w >= 800, f"Width {w} < 800 px"
        assert h >= 600, f"Height {h} < 600 px"

    def test_bar_chart_returns_base64(self, tmp_path: Path) -> None:
        """render_paper_figure must return a non-empty base64 PNG string."""
        import base64

        schema = _make_schema("bar")
        result = render_paper_figure(schema.model_dump(), tmp_path / "bar_b64.png")

        assert result.png_b64, "png_b64 must be non-empty"
        # Must decode cleanly to valid PNG bytes
        decoded = base64.b64decode(result.png_b64)
        assert decoded[:4] == b"\x89PNG", "Decoded base64 is not a PNG"


class TestLineChart:
    def test_line_chart_renders_valid_png(self, tmp_path: Path) -> None:
        schema = _make_schema("line")
        result = render_paper_figure(schema.model_dump(), tmp_path / "line.png")

        assert result.path.exists()
        img = Image.open(result.path)
        img.verify()

    def test_line_chart_dimensions(self, tmp_path: Path) -> None:
        schema = _make_schema("line")
        result = render_paper_figure(schema.model_dump(), tmp_path / "line_size.png")

        img = Image.open(result.path)
        w, h = img.size
        assert w >= 800, f"Width {w} < 800 px"
        assert h >= 600, f"Height {h} < 600 px"


class TestScatterChart:
    def test_scatter_chart_renders_valid_png(self, tmp_path: Path) -> None:
        schema = _make_schema("scatter")
        result = render_paper_figure(schema.model_dump(), tmp_path / "scatter.png")

        assert result.path.exists()
        img = Image.open(result.path)
        img.verify()

    def test_scatter_chart_dimensions(self, tmp_path: Path) -> None:
        schema = _make_schema("scatter")
        result = render_paper_figure(schema.model_dump(), tmp_path / "scatter_size.png")

        img = Image.open(result.path)
        w, h = img.size
        assert w >= 800, f"Width {w} < 800 px"
        assert h >= 600, f"Height {h} < 600 px"


class TestUnsupportedChartType:
    def test_unsupported_type_raises_value_error(self, tmp_path: Path) -> None:
        """render_paper_figure must raise ValueError for unknown chart types."""
        data = {
            "title": "Bad Chart",
            "chart_type": "pie",  # not supported
            "x_label": "X",
            "y_label": "Y",
            "series": [{"name": "S", "data": [{"x": "A", "y": 1.0}]}],
            "caption": "This should fail",
        }
        with pytest.raises(ValueError, match="Unsupported chart_type"):
            render_paper_figure(data, tmp_path / "bad.png")

    def test_histogram_raises_value_error(self, tmp_path: Path) -> None:
        data = {
            "title": "Histogram",
            "chart_type": "histogram",
            "x_label": "X",
            "y_label": "Count",
            "series": [],
            "caption": "Should raise",
        }
        with pytest.raises(ValueError):
            render_paper_figure(data, tmp_path / "hist.png")


class TestEmptyData:
    def test_bar_chart_empty_series_renders(self, tmp_path: Path) -> None:
        """Empty series must not crash — render a placeholder chart."""
        data = {
            "title": "Empty Bar",
            "chart_type": "bar",
            "x_label": "X",
            "y_label": "Y",
            "series": [],
            "caption": "No data",
        }
        result = render_paper_figure(data, tmp_path / "empty.png")
        assert result.path.exists()


class TestResultNamedTuple:
    def test_result_has_path_and_b64(self, tmp_path: Path) -> None:
        schema = _make_schema("bar", n_points=3, n_series=1)
        result = render_paper_figure(schema.model_dump(), tmp_path / "nt.png")

        assert hasattr(result, "path")
        assert hasattr(result, "png_b64")
        assert isinstance(result.path, Path)
        assert isinstance(result.png_b64, str)
