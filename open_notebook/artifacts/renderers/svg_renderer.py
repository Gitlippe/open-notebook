"""SVG + cairosvg infographic renderer.

Pipeline:
    InfographicSchema
        → Jinja2 renders ``infographic_default.svg.j2``
        → cairosvg converts SVG → PNG (2× scale → 2400×3600 px)
        → saved to ``output_path``

Also exposes ``render_html()`` for Phase-3 frontend inline preview.

Dependencies:
    cairosvg  — svg → png rasteriser (requires system libcairo)
    jinja2    — template engine
    Pillow    — used by downstream tests for pixel assertions only;
                not imported here to keep the render path lean.

If cairo is not available at import time (Docker build step, unit test
CI without the native lib) the module loads fine — cairo is only needed
when ``render()`` is actually called. Tests that cannot have cairosvg
installed should skip with ``pytest.importorskip("cairosvg")``.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

from jinja2 import Environment, PackageLoader, select_autoescape

if TYPE_CHECKING:
    # Only for type-checking; not imported at runtime to avoid hard crash
    # when cairosvg/cairo native library is absent.
    from open_notebook.artifacts.generators.infographic import InfographicSchema

# ---------------------------------------------------------------------------
# Jinja2 environment — loads templates from the assets/templates package
# ---------------------------------------------------------------------------
_TEMPLATE_PACKAGE = "open_notebook.artifacts.assets.templates"
_TEMPLATE_BASENAME = "infographic_default.svg.j2"

_jinja_env = Environment(
    loader=PackageLoader(
        "open_notebook.artifacts.assets",
        package_path="templates",
    ),
    autoescape=select_autoescape(["svg", "xml", "html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _get_template():
    return _jinja_env.get_template(_TEMPLATE_BASENAME)


# ---------------------------------------------------------------------------
# Color themes (mirrored here so render_html can use them directly)
# ---------------------------------------------------------------------------
_THEMES: Dict[str, Dict[str, str]] = {
    "blue": {
        "bg": "#0f172a", "panel": "#1e293b", "panel2": "#162032",
        "accent": "#38bdf8", "accent2": "#0ea5e9",
        "text": "#f1f5f9", "muted": "#94a3b8", "divider": "#334155",
    },
    "green": {
        "bg": "#052e16", "panel": "#064e3b", "panel2": "#073d2e",
        "accent": "#4ade80", "accent2": "#22c55e",
        "text": "#ecfdf5", "muted": "#86efac", "divider": "#166534",
    },
    "orange": {
        "bg": "#431407", "panel": "#7c2d12", "panel2": "#6b2510",
        "accent": "#fb923c", "accent2": "#f97316",
        "text": "#fff7ed", "muted": "#fdba74", "divider": "#9a3412",
    },
    "mono": {
        "bg": "#111827", "panel": "#1f2937", "panel2": "#18202c",
        "accent": "#e5e7eb", "accent2": "#d1d5db",
        "text": "#f9fafb", "muted": "#9ca3af", "divider": "#374151",
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _schema_to_dict(schema: "InfographicSchema") -> Dict[str, Any]:
    """Convert an InfographicSchema (or plain dict) to a template-ready dict."""
    if hasattr(schema, "model_dump"):
        return schema.model_dump()
    # Already a plain dict (convenience for tests / internal callers)
    return dict(schema)


def render_svg(schema: Union["InfographicSchema", Dict[str, Any]], theme: Optional[str] = None) -> str:
    """Render the schema to an SVG string.

    Parameters
    ----------
    schema:
        An ``InfographicSchema`` Pydantic model or a plain dict.
    theme:
        Override the color_theme; if None, uses schema.color_theme.

    Returns
    -------
    str
        Complete SVG document as a UTF-8 string.
    """
    data = _schema_to_dict(schema)
    resolved_theme = (theme or data.get("color_theme") or "blue").lower()
    if resolved_theme not in _THEMES:
        resolved_theme = "blue"

    tmpl = _get_template()
    return tmpl.render(
        title=data.get("title", "Infographic"),
        subtitle=data.get("subtitle") or "",
        sections=data.get("sections") or [],
        stats=data.get("stats") or [],
        color_theme=resolved_theme,
    )


def render(
    schema: Union["InfographicSchema", Dict[str, Any]],
    output_path: Path,
    theme: Optional[str] = None,
    scale: float = 2.0,
) -> Path:
    """Render the infographic schema to a PNG file.

    The SVG is rendered at 1200×1800 SVG units; ``scale`` multiplies the
    output PNG resolution (default 2× → 2400×3600 px, ~200 dpi).

    Parameters
    ----------
    schema:
        ``InfographicSchema`` model or equivalent dict.
    output_path:
        Destination ``.png`` file path.  Parent directories are created.
    theme:
        Color theme override.
    scale:
        DPI multiplier for the PNG rasteriser.

    Returns
    -------
    Path
        The ``output_path`` that was written.
    """
    try:
        import cairosvg  # noqa: F401 — lazy import keeps module loadable without cairo
    except OSError as exc:
        raise RuntimeError(
            "cairosvg requires the system 'cairo' native library. "
            "On macOS: `brew install cairo`. "
            "On Debian/Ubuntu: `apt-get install libcairo2`. "
            f"Original error: {exc}"
        ) from exc

    svg_text = render_svg(schema, theme=theme)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    png_bytes = cairosvg.svg2png(
        bytestring=svg_text.encode("utf-8"),
        scale=scale,
        unsafe=False,
    )
    output_path.write_bytes(png_bytes)
    return output_path


def render_html(
    schema: Union["InfographicSchema", Dict[str, Any]],
    theme: Optional[str] = None,
) -> str:
    """Return a self-contained HTML string for Phase-3 frontend preview.

    The SVG is inlined directly into the HTML so a browser can render it
    without any external resources.

    Parameters
    ----------
    schema:
        ``InfographicSchema`` model or equivalent dict.
    theme:
        Color theme override.

    Returns
    -------
    str
        Complete HTML document embedding the infographic SVG.
    """
    data = _schema_to_dict(schema)
    resolved_theme = (theme or data.get("color_theme") or "blue").lower()
    t = _THEMES.get(resolved_theme, _THEMES["blue"])

    svg_content = render_svg(schema, theme=theme)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{data.get('title', 'Infographic')} — Open Notebook</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: {t['bg']};
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: 24px;
    }}
    .infographic-wrap {{
      max-width: 800px;
      width: 100%;
      border-radius: 16px;
      overflow: hidden;
      box-shadow: 0 24px 48px rgba(0,0,0,0.5);
    }}
    .infographic-wrap svg {{
      width: 100%;
      height: auto;
      display: block;
    }}
  </style>
</head>
<body>
  <div class="infographic-wrap">
    {svg_content}
  </div>
</body>
</html>"""
