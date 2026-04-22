"""Integration tests for svg_renderer.py.

Tests the SVG→PNG pipeline using hand-constructed InfographicSchema fixtures.
No LLM calls are made.

Markers: integration
Run: uv run pytest tests/artifacts/integration/renderers/test_svg_renderer.py -m integration -v

Note: cairosvg requires the system 'cairo' native library.
If cairo is not installed these tests are skipped automatically.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

# Skip module-level if cairosvg cannot load cairo native lib
cairosvg = pytest.importorskip("cairosvg", reason="cairosvg not available — skipping SVG renderer tests")

try:
    # Trigger the actual cairo dynamic library load (fails if libcairo absent)
    import cairosvg.surface  # noqa: F401
except OSError as _cairo_err:
    pytest.skip(f"libcairo native library not found: {_cairo_err}", allow_module_level=True)

from PIL import Image


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def infographic_dict_blue():
    return {
        "title": "AI Research Highlights 2025",
        "subtitle": "A snapshot of breakthrough methods this year",
        "sections": [
            {"heading": "Training-Free Optimization", "text": "Prompt-based RL achieves GRPO-quality results without parameter updates, using 100× less data."},
            {"heading": "Multimodal Advances", "text": "Vision-language models now process video natively, enabling real-time scene understanding."},
            {"heading": "Inference Efficiency", "text": "Speculative decoding cuts token latency by 3× on commodity GPUs."},
            {"heading": "Safety & Alignment", "text": "Constitutional AI v2 reduces harmful outputs by 40% while maintaining task performance."},
        ],
        "stats": [
            {"value": "82%", "label": "AIME 2024 accuracy"},
            {"value": "100×", "label": "Less training data"},
            {"value": "3×", "label": "Inference speedup"},
        ],
        "color_theme": "blue",
    }


@pytest.fixture
def infographic_schema():
    """A full InfographicSchema Pydantic model."""
    from open_notebook.artifacts.generators.infographic import (
        InfographicSchema,
        InfographicSectionSchema,
        InfographicStatSchema,
    )
    return InfographicSchema(
        title="Pydantic Schema Test",
        subtitle="Testing Pydantic model input to svg_renderer",
        sections=[
            InfographicSectionSchema(heading="Section One", text="Detailed body for section one."),
            InfographicSectionSchema(heading="Section Two", text="Detailed body for section two."),
            InfographicSectionSchema(heading="Section Three", text="Detailed body for section three."),
            InfographicSectionSchema(heading="Section Four", text="Detailed body for section four."),
        ],
        stats=[
            InfographicStatSchema(value="99%", label="Accuracy"),
            InfographicStatSchema(value="10×", label="Speed gain"),
            InfographicStatSchema(value="$2B", label="Market size"),
        ],
        color_theme="blue",
    )


def _make_data(theme: str):
    return {
        "title": f"Theme Test: {theme.title()}",
        "subtitle": f"Testing the {theme} color theme",
        "sections": [
            {"heading": "Point One", "text": "Content for the first point in this infographic layout."},
            {"heading": "Point Two", "text": "Content for the second point in this infographic layout."},
        ],
        "stats": [
            {"value": "42%", "label": "Metric Alpha"},
            {"value": "7×", "label": "Metric Beta"},
        ],
        "color_theme": theme,
    }


def _hex_to_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _dominant_bg(img: Image.Image, radius: int = 20) -> tuple:
    """Sample the average RGB in the top-left corner (background area)."""
    region = img.crop((10, 10, 10 + 2 * radius, 10 + 2 * radius)).convert("RGB")
    pixels = list(region.getdata())
    r = sum(p[0] for p in pixels) // len(pixels)
    g = sum(p[1] for p in pixels) // len(pixels)
    b = sum(p[2] for p in pixels) // len(pixels)
    return (r, g, b)


def _color_dist(c1: tuple, c2: tuple) -> float:
    return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5


# ---------------------------------------------------------------------------
# Tests — SVG string output
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestRenderSvg:
    """Test the render_svg() function that returns an SVG string."""

    def test_returns_string(self, infographic_dict_blue):
        from open_notebook.artifacts.renderers.svg_renderer import render_svg
        result = render_svg(infographic_dict_blue)
        assert isinstance(result, str)

    def test_contains_svg_root(self, infographic_dict_blue):
        from open_notebook.artifacts.renderers.svg_renderer import render_svg
        svg = render_svg(infographic_dict_blue)
        assert "<svg" in svg
        assert "</svg>" in svg

    def test_title_in_svg(self, infographic_dict_blue):
        from open_notebook.artifacts.renderers.svg_renderer import render_svg
        svg = render_svg(infographic_dict_blue)
        assert "AI Research Highlights" in svg

    def test_stats_in_svg(self, infographic_dict_blue):
        from open_notebook.artifacts.renderers.svg_renderer import render_svg
        svg = render_svg(infographic_dict_blue)
        assert "82%" in svg
        assert "100" in svg

    def test_accepts_pydantic_schema(self, infographic_schema):
        from open_notebook.artifacts.renderers.svg_renderer import render_svg
        svg = render_svg(infographic_schema)
        assert "Pydantic Schema Test" in svg

    def test_theme_override(self, infographic_dict_blue):
        from open_notebook.artifacts.renderers.svg_renderer import render_svg
        svg_blue = render_svg(infographic_dict_blue, theme="blue")
        svg_green = render_svg(infographic_dict_blue, theme="green")
        # Green theme has different colors — they shouldn't be identical SVGs
        assert svg_blue != svg_green
        assert "#4ade80" in svg_green  # green accent
        assert "#38bdf8" in svg_blue   # blue accent

    def test_all_themes_produce_valid_svg(self):
        from open_notebook.artifacts.renderers.svg_renderer import render_svg
        for theme in ("blue", "green", "orange", "mono"):
            data = _make_data(theme)
            svg = render_svg(data)
            assert "<svg" in svg, f"Theme {theme}: no <svg> tag found"
            assert theme.upper() in svg, f"Theme {theme}: badge text not found in SVG"


# ---------------------------------------------------------------------------
# Tests — PNG rendering via cairosvg
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestRenderPng:
    """Test the render() function that produces a PNG file."""

    def test_creates_png_file(self, infographic_dict_blue, tmp_path):
        from open_notebook.artifacts.renderers.svg_renderer import render
        out = tmp_path / "test_blue.png"
        result = render(infographic_dict_blue, out)
        assert result == out
        assert out.exists()
        assert out.stat().st_size > 100_000  # substantial PNG

    def test_output_dimensions_at_2x_scale(self, infographic_dict_blue, tmp_path):
        """Default scale=2.0 → 2400×3600 output from 1200×1800 SVG."""
        from open_notebook.artifacts.renderers.svg_renderer import render
        out = tmp_path / "scale2x.png"
        render(infographic_dict_blue, out, scale=2.0)
        with Image.open(out) as img:
            w, h = img.size
        assert w >= 2000, f"Width {w} too small for 2× scale"
        assert h >= 3000, f"Height {h} too small for 2× scale"

    def test_output_at_1x_scale_min_1080(self, infographic_dict_blue, tmp_path):
        """1× scale → at least 1200×1800; both ≥ 1080."""
        from open_notebook.artifacts.renderers.svg_renderer import render
        out = tmp_path / "scale1x.png"
        render(infographic_dict_blue, out, scale=1.0)
        with Image.open(out) as img:
            w, h = img.size
        assert w >= 1080
        assert h >= 1080

    def test_blue_theme_background_color(self, tmp_path):
        """Blue theme background should be close to #0f172a."""
        from open_notebook.artifacts.renderers.svg_renderer import render
        data = _make_data("blue")
        out = tmp_path / "bg_blue.png"
        render(data, out, scale=1.0)
        with Image.open(out) as img:
            sampled = _dominant_bg(img)
        expected = _hex_to_rgb("#0f172a")
        dist = _color_dist(sampled, expected)
        assert dist < 80, f"Blue bg pixel {sampled} far from expected {expected} (dist={dist:.1f})"

    def test_green_theme_background_color(self, tmp_path):
        """Green theme background should be close to #052e16."""
        from open_notebook.artifacts.renderers.svg_renderer import render
        data = _make_data("green")
        out = tmp_path / "bg_green.png"
        render(data, out, scale=1.0)
        with Image.open(out) as img:
            sampled = _dominant_bg(img)
        expected = _hex_to_rgb("#052e16")
        dist = _color_dist(sampled, expected)
        assert dist < 80, f"Green bg pixel {sampled} far from expected {expected} (dist={dist:.1f})"

    def test_orange_theme_background_color(self, tmp_path):
        """Orange theme background should be close to #431407."""
        from open_notebook.artifacts.renderers.svg_renderer import render
        data = _make_data("orange")
        out = tmp_path / "bg_orange.png"
        render(data, out, scale=1.0)
        with Image.open(out) as img:
            sampled = _dominant_bg(img)
        expected = _hex_to_rgb("#431407")
        dist = _color_dist(sampled, expected)
        assert dist < 80, f"Orange bg pixel {sampled} far from expected {expected} (dist={dist:.1f})"

    def test_mono_theme_background_color(self, tmp_path):
        """Mono theme background should be close to #111827."""
        from open_notebook.artifacts.renderers.svg_renderer import render
        data = _make_data("mono")
        out = tmp_path / "bg_mono.png"
        render(data, out, scale=1.0)
        with Image.open(out) as img:
            sampled = _dominant_bg(img)
        expected = _hex_to_rgb("#111827")
        dist = _color_dist(sampled, expected)
        assert dist < 80, f"Mono bg pixel {sampled} far from expected {expected} (dist={dist:.1f})"

    def test_all_themes_produce_distinguishable_output(self, tmp_path):
        """Different themes must produce measurably different accent bar colors.

        The top accent bar (8px high at y=0) uses each theme's accent gradient
        and is clearly distinguishable. We avoid comparing background colors
        for blue vs mono since both are intentionally dark navy/charcoal.
        """
        from open_notebook.artifacts.renderers.svg_renderer import render

        def sample_top_bar(img: Image.Image) -> tuple:
            """Sample the accent bar at the very top of the image (y≈4)."""
            cx = img.width // 2
            region = img.crop((cx - 20, 2, cx + 20, 10)).convert("RGB")
            pixels = list(region.getdata())
            return tuple(sum(p[i] for p in pixels) // len(pixels) for i in range(3))

        sampled: dict[str, tuple] = {}
        for theme in ("blue", "green", "orange", "mono"):
            data = _make_data(theme)
            out = tmp_path / f"dist_{theme}.png"
            render(data, out, scale=1.0)
            with Image.open(out) as img:
                sampled[theme] = sample_top_bar(img)

        themes = list(sampled.keys())
        for i, t1 in enumerate(themes):
            for t2 in themes[i + 1:]:
                dist = _color_dist(sampled[t1], sampled[t2])
                assert dist > 25, (
                    f"Themes {t1} and {t2} accent bars indistinguishable: "
                    f"{sampled[t1]} vs {sampled[t2]} (dist={dist:.1f})"
                )

    def test_accepts_pydantic_schema(self, infographic_schema, tmp_path):
        from open_notebook.artifacts.renderers.svg_renderer import render
        out = tmp_path / "pydantic_schema.png"
        result = render(infographic_schema, out, scale=1.0)
        assert out.exists()
        with Image.open(out) as img:
            assert img.size[0] >= 1080

    def test_creates_parent_directories(self, infographic_dict_blue, tmp_path):
        from open_notebook.artifacts.renderers.svg_renderer import render
        nested = tmp_path / "a" / "b" / "c" / "infographic.png"
        render(infographic_dict_blue, nested, scale=1.0)
        assert nested.exists()

    def test_png_is_valid_image(self, infographic_dict_blue, tmp_path):
        """Verify cairosvg produced a valid, openable PIL image."""
        from open_notebook.artifacts.renderers.svg_renderer import render
        out = tmp_path / "valid.png"
        render(infographic_dict_blue, out, scale=1.0)
        with Image.open(out) as img:
            img.verify()  # raises if corrupt


# ---------------------------------------------------------------------------
# Tests — render_html
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestRenderHtml:
    """Test the render_html() function."""

    def test_returns_html_string(self, infographic_dict_blue):
        from open_notebook.artifacts.renderers.svg_renderer import render_html
        html = render_html(infographic_dict_blue)
        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html

    def test_embeds_svg_inline(self, infographic_dict_blue):
        from open_notebook.artifacts.renderers.svg_renderer import render_html
        html = render_html(infographic_dict_blue)
        assert "<svg" in html

    def test_contains_title(self, infographic_dict_blue):
        from open_notebook.artifacts.renderers.svg_renderer import render_html
        html = render_html(infographic_dict_blue)
        assert "AI Research Highlights" in html

    def test_theme_override_changes_output(self, infographic_dict_blue):
        from open_notebook.artifacts.renderers.svg_renderer import render_html
        html_blue = render_html(infographic_dict_blue, theme="blue")
        html_orange = render_html(infographic_dict_blue, theme="orange")
        assert html_blue != html_orange

    def test_accepts_pydantic_schema(self, infographic_schema):
        from open_notebook.artifacts.renderers.svg_renderer import render_html
        html = render_html(infographic_schema)
        assert "Pydantic Schema Test" in html
