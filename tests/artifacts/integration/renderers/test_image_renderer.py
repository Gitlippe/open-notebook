"""Integration tests for image_renderer.py.

These tests exercise the Pillow-based fallback renderer with bundled fonts.
They do NOT make LLM calls — all schemas are hand-constructed.

Markers: integration
Run: uv run pytest tests/artifacts/integration/renderers/test_image_renderer.py -m integration -v
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageFont

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def infographic_data_blue():
    return {
        "title": "AI Research Highlights 2025",
        "subtitle": "A snapshot of breakthrough methods this year",
        "sections": [
            {"heading": "Training-Free Optimization", "text": "Prompt-based RL achieves GRPO-quality results without parameter updates, using 100× less data."},
            {"heading": "Multimodal Advances", "text": "Vision-language models now process video natively, enabling real-time scene understanding at scale."},
            {"heading": "Inference Efficiency", "text": "Speculative decoding cuts token latency by 3× on commodity GPUs, democratizing LLM access."},
            {"heading": "Safety & Alignment", "text": "Constitutional AI v2 reduces harmful outputs by 40% while maintaining task performance parity."},
        ],
        "stats": [
            {"value": "82%", "label": "AIME 2024 score improvement"},
            {"value": "100×", "label": "Less training data needed"},
            {"value": "3×", "label": "Faster inference throughput"},
        ],
        "color_theme": "blue",
    }


@pytest.fixture
def make_infographic_data():
    """Factory for infographic data with a specific theme."""
    def _make(theme: str):
        return {
            "title": f"Test Infographic ({theme.title()})",
            "subtitle": f"Testing the {theme} color theme",
            "sections": [
                {"heading": "Section One", "text": "This is the first section body text with sufficient content for layout testing."},
                {"heading": "Section Two", "text": "Second section provides more content to verify multi-section rendering."},
            ],
            "stats": [
                {"value": "42%", "label": "Key metric A"},
                {"value": "7×", "label": "Key metric B"},
                {"value": "$1.2B", "label": "Key metric C"},
            ],
            "color_theme": theme,
        }
    return _make


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dominant_color_at(img: Image.Image, x: int, y: int, radius: int = 5) -> tuple:
    """Sample average RGB in a small patch around (x, y)."""
    region = img.crop((x - radius, y - radius, x + radius, y + radius))
    region = region.convert("RGB")
    pixels = list(region.getdata())
    r = sum(p[0] for p in pixels) // len(pixels)
    g = sum(p[1] for p in pixels) // len(pixels)
    b = sum(p[2] for p in pixels) // len(pixels)
    return (r, g, b)


def _hex_to_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _color_distance(c1: tuple, c2: tuple) -> float:
    """Euclidean distance in RGB space."""
    return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5


# ---------------------------------------------------------------------------
# Tests — bundled font loading
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestBundledFonts:
    """Verify Inter fonts are bundled and loadable via importlib.resources."""

    def test_inter_regular_loads(self):
        from open_notebook.artifacts.renderers.image_renderer import _load_font
        font = _load_font(24, "Regular")
        # Must not be the fallback bitmap default
        assert isinstance(font, ImageFont.FreeTypeFont), \
            "Expected FreeTypeFont (truetype), got default bitmap — bundled font missing?"

    def test_inter_bold_loads(self):
        from open_notebook.artifacts.renderers.image_renderer import _load_font
        font = _load_font(36, "Bold")
        assert isinstance(font, ImageFont.FreeTypeFont)

    def test_inter_semibold_loads(self):
        from open_notebook.artifacts.renderers.image_renderer import _load_font
        font = _load_font(28, "SemiBold")
        assert isinstance(font, ImageFont.FreeTypeFont)

    def test_bundled_font_path_resolves(self):
        from open_notebook.artifacts.renderers.image_renderer import _bundled_font_path
        for variant in ("Regular", "Bold", "SemiBold"):
            path = _bundled_font_path(variant)
            assert path is not None, f"Bundled font path for {variant} is None"
            assert Path(path).exists(), f"Bundled font file does not exist: {path}"
            assert Path(path).suffix.lower() == ".ttf"


# ---------------------------------------------------------------------------
# Tests — Pillow renderer (force prefer_svg=False)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestPillowRenderer:
    """Test the pure-Pillow fallback renderer with bundled fonts."""

    def test_renders_blue_png(self, infographic_data_blue, tmp_path):
        from open_notebook.artifacts.renderers.image_renderer import render_infographic
        out = tmp_path / "test_blue.png"
        result = render_infographic(infographic_data_blue, out, prefer_svg=False)
        assert result == out
        assert out.exists()
        assert out.stat().st_size > 50_000  # non-trivial PNG

    def test_output_size_minimum_1080x1080(self, infographic_data_blue, tmp_path):
        from open_notebook.artifacts.renderers.image_renderer import render_infographic
        out = tmp_path / "size_check.png"
        render_infographic(infographic_data_blue, out, prefer_svg=False)
        with Image.open(out) as img:
            w, h = img.size
        assert w >= 1080, f"Width {w} < 1080"
        assert h >= 1080, f"Height {h} < 1080"

    def test_blue_theme_header_color(self, infographic_data_blue, tmp_path):
        """The header region should be close to the blue background color."""
        from open_notebook.artifacts.renderers.image_renderer import render_infographic
        out = tmp_path / "blue_header.png"
        render_infographic(infographic_data_blue, out, prefer_svg=False)
        with Image.open(out) as img:
            # Sample the background color in the top-left corner (padding area)
            sampled = _dominant_color_at(img, 30, 30, radius=10)
        expected_bg = _hex_to_rgb("#0f172a")
        dist = _color_distance(sampled, expected_bg)
        assert dist < 60, f"Blue theme bg pixel {sampled} far from expected {expected_bg} (dist={dist:.1f})"

    def test_all_four_themes_render(self, make_infographic_data, tmp_path):
        """All four themes must render without error and produce valid PNGs."""
        from open_notebook.artifacts.renderers.image_renderer import render_infographic
        for theme in ("blue", "green", "orange", "mono"):
            data = make_infographic_data(theme)
            out = tmp_path / f"theme_{theme}.png"
            result = render_infographic(data, out, prefer_svg=False)
            assert out.exists(), f"PNG not created for theme {theme}"
            with Image.open(out) as img:
                assert img.format == "PNG"
                assert img.size[0] >= 1080

    def test_themes_produce_distinguishable_backgrounds(self, tmp_path):
        """Different themes must produce measurably different accent-colored regions.

        We scan the title area (y≈60–120) for the brightest pixel cluster,
        which corresponds to the accent-colored title text. Blue/mono share
        similar dark backgrounds, but their accent colors (#38bdf8 vs #e5e7eb)
        are clearly distinguishable in the title region.
        """
        from open_notebook.artifacts.renderers.image_renderer import render_infographic

        def sample_brightest(img: Image.Image, search_y: int = 90, radius: int = 15) -> tuple:
            """Return the average color in a patch at the title text row."""
            # Title is rendered at y=padding=60 in the Pillow renderer;
            # at y≈90 we're in the middle of the first title glyph row.
            cx = img.width // 4  # left portion where long title text falls
            region = img.crop((cx - radius, search_y - radius, cx + radius, search_y + radius))
            region = region.convert("RGB")
            pixels = list(region.getdata())
            return tuple(sum(p[i] for p in pixels) // len(pixels) for i in range(3))

        sampled: dict[str, tuple] = {}
        for theme in ("blue", "green", "orange", "mono"):
            data = {
                "title": "WWWWWWWWWWWWWWWW",  # wide title ensures accent pixels fill sampling area
                "subtitle": "",
                "sections": [{"heading": "A", "text": "Body text"}],
                "stats": [{"value": "99%", "label": "metric"}],
                "color_theme": theme,
            }
            out = tmp_path / f"accent_{theme}.png"
            render_infographic(data, out, prefer_svg=False)
            with Image.open(out) as img:
                sampled[theme] = sample_brightest(img)

        # Each pair of themes must differ by at least 40 units in RGB space
        themes = list(sampled.keys())
        for i, t1 in enumerate(themes):
            for t2 in themes[i + 1:]:
                dist = _color_distance(sampled[t1], sampled[t2])
                assert dist > 20, (
                    f"Themes {t1} and {t2} accent title regions indistinguishable "
                    f"({sampled[t1]} vs {sampled[t2]}, dist={dist:.1f})"
                )

    def test_renders_schema_pydantic_model(self, tmp_path):
        """render_infographic should also accept an InfographicSchema Pydantic model."""
        from open_notebook.artifacts.generators.infographic import InfographicSchema, InfographicSectionSchema, InfographicStatSchema
        from open_notebook.artifacts.renderers.image_renderer import render_infographic
        schema = InfographicSchema(
            title="Pydantic Model Test",
            subtitle="Testing Pydantic input path",
            sections=[
                InfographicSectionSchema(heading="Sec A", text="Body A"),
                InfographicSectionSchema(heading="Sec B", text="Body B"),
            ],
            stats=[
                InfographicStatSchema(value="99%", label="Test metric"),
            ],
            color_theme="green",
        )
        out = tmp_path / "pydantic_test.png"
        render_infographic(schema, out, prefer_svg=False)
        assert out.exists()
        with Image.open(out) as img:
            assert img.size[0] >= 1080


# ---------------------------------------------------------------------------
# Tests — HTML renderer
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestHtmlRenderer:
    """Test the HTML output path."""

    def test_renders_html_file(self, infographic_data_blue, tmp_path):
        from open_notebook.artifacts.renderers.image_renderer import render_infographic_html
        out = tmp_path / "infographic.html"
        result = render_infographic_html(infographic_data_blue, out)
        assert out.exists()
        content = out.read_text()
        assert "<svg" in content or "<!DOCTYPE html>" in content
        assert "AI Research Highlights" in content

    def test_html_contains_title(self, infographic_data_blue, tmp_path):
        from open_notebook.artifacts.renderers.image_renderer import render_infographic_html
        out = tmp_path / "html_title.html"
        render_infographic_html(infographic_data_blue, out)
        assert "AI Research Highlights" in out.read_text()
