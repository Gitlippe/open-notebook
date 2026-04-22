"""Pillow-based image renderer for infographics and simple PNG artifacts.

Design
------
- **Infographics** are delegated to :mod:`svg_renderer` (SVG → cairosvg → PNG)
  for professional, high-fidelity output.
- **Simple PNGs** (timelines, paper-figure fallback) continue to use Pillow
  with *bundled* Inter fonts loaded via ``importlib.resources`` — no
  hard-coded system paths, works on macOS, Linux, and Docker alike.

Font resolution order
---------------------
1. ``importlib.resources`` — bundled ``Inter-{Regular,Bold,SemiBold}.ttf``
   shipped in the ``open_notebook.artifacts.assets.fonts`` package.
2. Graceful fallback to Pillow's built-in bitmap default only if the
   bundled TTF cannot be opened (should never happen in normal installs).

Public API
----------
``render_infographic(schema, output_path) -> Path``
    Render a complete infographic PNG (delegates to svg_renderer when
    cairosvg/cairo is available; falls back to Pillow-based rendering
    when cairo is absent, e.g. in unit-test CI without the native lib).

``render_infographic_html(schema, output_path) -> Path``
    Write a self-contained HTML file embedding the infographic (delegates
    to svg_renderer.render_html()).

Both functions accept either a Pydantic ``InfographicSchema`` or a plain
``dict`` for backward compatibility with the generator.
"""
from __future__ import annotations

import textwrap
from importlib.resources import files as _resource_files
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import Image, ImageDraw, ImageFont
from loguru import logger


# ---------------------------------------------------------------------------
# Color themes — identical to svg_renderer._THEMES for consistency
# ---------------------------------------------------------------------------
_THEMES: Dict[str, Dict[str, str]] = {
    "blue": {
        "bg": "#0f172a", "panel": "#1e293b", "accent": "#38bdf8",
        "text": "#f1f5f9", "muted": "#94a3b8",
    },
    "green": {
        "bg": "#052e16", "panel": "#064e3b", "accent": "#4ade80",
        "text": "#ecfdf5", "muted": "#86efac",
    },
    "orange": {
        "bg": "#431407", "panel": "#7c2d12", "accent": "#fb923c",
        "text": "#fff7ed", "muted": "#fdba74",
    },
    "mono": {
        "bg": "#111827", "panel": "#1f2937", "accent": "#e5e7eb",
        "text": "#f9fafb", "muted": "#9ca3af",
    },
}

_FONTS_PKG = "open_notebook.artifacts.assets.fonts"


# ---------------------------------------------------------------------------
# Font helpers — bundled Inter via importlib.resources
# ---------------------------------------------------------------------------

def _bundled_font_path(variant: str) -> Optional[str]:
    """Return an absolute path to a bundled Inter TTF, or None on failure."""
    filename = f"Inter-{variant}.ttf"
    try:
        resource = _resource_files(_FONTS_PKG) / filename
        # importlib.resources may return a Traversable; materialise to str
        # by converting through Path if possible
        font_path = str(resource)
        # Verify the file is actually readable
        with open(font_path, "rb"):
            pass
        return font_path
    except Exception as exc:
        logger.warning("Could not resolve bundled font {}: {}", filename, exc)
        return None


def _load_font(size: int, variant: str = "Regular") -> ImageFont.FreeTypeFont:
    """Load a bundled Inter font at the given pixel size.

    Falls back to Pillow's built-in default if the TTF file is missing.
    """
    path = _bundled_font_path(variant)
    if path:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception as exc:
            logger.warning("truetype load failed for {}: {}", path, exc)
    logger.warning("Falling back to Pillow default bitmap font (size ignored)")
    return ImageFont.load_default()


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _text_size(draw: ImageDraw.ImageDraw, text: str, font) -> Tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _wrap(text: str, width: int) -> List[str]:
    return textwrap.wrap(text, width=width) or [""]


def _schema_to_dict(schema: Any) -> Dict[str, Any]:
    if hasattr(schema, "model_dump"):
        return schema.model_dump()
    return dict(schema)


# ---------------------------------------------------------------------------
# Pillow-based infographic renderer (fallback when cairo unavailable)
# ---------------------------------------------------------------------------

def _render_infographic_pillow(data: Dict[str, Any], path: Path) -> Path:
    """Pure-Pillow fallback renderer — uses bundled Inter fonts."""
    theme_name = (data.get("color_theme") or "blue").lower()
    theme = _THEMES.get(theme_name, _THEMES["blue"])

    W, H = 1200, 1800
    img = Image.new("RGB", (W, H), _hex_to_rgb(theme["bg"]))
    draw = ImageDraw.Draw(img)

    title = data.get("title", "Infographic")
    subtitle = data.get("subtitle", "")
    sections: List[Dict[str, Any]] = data.get("sections") or []
    stats: List[Dict[str, Any]] = data.get("stats") or []

    # Fonts — bundled Inter
    title_font = _load_font(58, "Bold")
    subtitle_font = _load_font(26, "Regular")
    h_font = _load_font(30, "SemiBold")
    body_font = _load_font(22, "Regular")
    stat_num_font = _load_font(54, "Bold")
    stat_label_font = _load_font(20, "Regular")

    padding = 60
    y = padding

    # Title
    for line in _wrap(title, 30):
        draw.text((padding, y), line, font=title_font, fill=_hex_to_rgb(theme["accent"]))
        _, h = _text_size(draw, line, title_font)
        y += h + 6
    y += 16

    # Subtitle
    if subtitle:
        for line in _wrap(subtitle, 60):
            draw.text((padding, y), line, font=subtitle_font, fill=_hex_to_rgb(theme["muted"]))
            _, h = _text_size(draw, line, subtitle_font)
            y += h + 4
        y += 24

    # Divider
    draw.rectangle([(padding, y), (W - padding, y + 4)], fill=_hex_to_rgb(theme["accent"]))
    y += 40

    # Stats band
    if stats:
        stats_top = y
        panel_h = 180
        draw.rectangle(
            [(padding, y), (W - padding, y + panel_h)],
            fill=_hex_to_rgb(theme["panel"]),
        )
        cols = min(len(stats), 4)
        col_w = (W - 2 * padding) // cols
        for i, st in enumerate(stats[:cols]):
            cx = padding + i * col_w + col_w // 2
            value = str(st.get("value", ""))
            label = str(st.get("label", ""))
            v_w, v_h = _text_size(draw, value, stat_num_font)
            draw.text(
                (cx - v_w // 2, y + 36), value,
                font=stat_num_font, fill=_hex_to_rgb(theme["accent"]),
            )
            for li, ln in enumerate(_wrap(label, 18)[:2]):
                l_w, l_h = _text_size(draw, ln, stat_label_font)
                draw.text(
                    (cx - l_w // 2, y + 36 + v_h + 10 + li * (l_h + 2)),
                    ln, font=stat_label_font, fill=_hex_to_rgb(theme["text"]),
                )
        y = stats_top + panel_h + 40

    # Content sections
    for sect in sections[:6]:
        heading = sect.get("heading", "")
        body = sect.get("text", "")
        draw.text((padding, y), heading, font=h_font, fill=_hex_to_rgb(theme["accent"]))
        _, h = _text_size(draw, heading, h_font)
        y += h + 10
        for line in _wrap(body, 70):
            if y + 32 > H - padding:
                break
            draw.text((padding, y), line, font=body_font, fill=_hex_to_rgb(theme["text"]))
            _, lh = _text_size(draw, line, body_font)
            y += lh + 4
        y += 24
        if y > H - padding - 60:
            break

    # Footer
    footer = "Generated by Open Notebook"
    f_w, f_h = _text_size(draw, footer, stat_label_font)
    draw.text(
        (W - padding - f_w, H - padding - f_h),
        footer, font=stat_label_font, fill=_hex_to_rgb(theme["muted"]),
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(path), format="PNG")
    return path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_infographic(
    schema: Union[Any, Dict[str, Any]],
    path: Path,
    *,
    prefer_svg: bool = True,
) -> Path:
    """Render an infographic to a PNG file.

    Attempts the SVG → cairosvg pipeline (``prefer_svg=True`` by default) for
    professional quality output.  Falls back automatically to the Pillow
    renderer if cairosvg / libcairo is not available in the current
    environment.

    Parameters
    ----------
    schema:
        An ``InfographicSchema`` Pydantic model **or** a plain dict
        (backward-compatible with the Phase-0 renderer contract).
    path:
        Destination PNG file path.
    prefer_svg:
        If True (default) and cairosvg is importable, use the SVG pipeline.
        Set to False to force the Pillow renderer (useful in tests).

    Returns
    -------
    Path
        The written PNG file path.
    """
    data = _schema_to_dict(schema)
    path = Path(path)

    if prefer_svg:
        try:
            from open_notebook.artifacts.renderers import svg_renderer
            return svg_renderer.render(data, path)
        except (ImportError, OSError, RuntimeError) as exc:
            logger.warning(
                "SVG renderer unavailable ({}); falling back to Pillow.", exc
            )

    return _render_infographic_pillow(data, path)


def render_infographic_html(
    schema: Union[Any, Dict[str, Any]],
    path: Path,
) -> Path:
    """Write a self-contained HTML preview of the infographic.

    Delegates to :func:`svg_renderer.render_html` for the SVG-based
    preview; falls back to a Pillow-agnostic basic HTML on failure.

    Parameters
    ----------
    schema:
        An ``InfographicSchema`` Pydantic model or plain dict.
    path:
        Destination ``.html`` file path.

    Returns
    -------
    Path
        The written HTML file path.
    """
    data = _schema_to_dict(schema)
    path = Path(path)

    try:
        from open_notebook.artifacts.renderers import svg_renderer
        html_content = svg_renderer.render_html(data)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html_content, encoding="utf-8")
        return path
    except (ImportError, OSError, RuntimeError) as exc:
        logger.warning("SVG render_html unavailable ({}); using basic HTML.", exc)

    # Basic HTML fallback
    theme_name = (data.get("color_theme") or "blue").lower()
    theme = _THEMES.get(theme_name, _THEMES["blue"])
    sections = data.get("sections") or []
    stats = data.get("stats") or []

    sections_html = "\n".join(
        f'<section><h2>{s.get("heading", "")}</h2><p>{s.get("text", "")}</p></section>'
        for s in sections
    )
    stats_html = "\n".join(
        f'<div class="stat"><div class="num">{s.get("value", "")}</div>'
        f'<div class="lbl">{s.get("label", "")}</div></div>'
        for s in stats
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"><title>{data.get('title', 'Infographic')}</title>
<style>
  body {{ background: {theme['bg']}; color: {theme['text']};
         font-family: -apple-system, system-ui, sans-serif; padding: 48px; }}
  h1 {{ color: {theme['accent']}; font-size: 48px; margin: 0 0 12px; }}
  h2 {{ color: {theme['accent']}; margin-top: 32px; }}
  .stats {{ display: flex; gap: 24px; background: {theme['panel']};
            padding: 24px; border-radius: 16px; margin: 24px 0; }}
  .stat {{ flex: 1; text-align: center; }}
  .num {{ font-size: 42px; font-weight: 700; color: {theme['accent']}; }}
  .lbl {{ color: {theme['muted']}; margin-top: 4px; }}
  section {{ background: {theme['panel']}; padding: 16px 24px;
             border-radius: 12px; margin: 16px 0; }}
</style>
</head>
<body>
<h1>{data.get('title', 'Infographic')}</h1>
<p style="color:{theme['muted']}">{data.get('subtitle', '')}</p>
<div class="stats">{stats_html}</div>
{sections_html}
<footer style="margin-top:48px;color:{theme['muted']};font-size:12px;">
  Generated by Open Notebook
</footer>
</body></html>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path
