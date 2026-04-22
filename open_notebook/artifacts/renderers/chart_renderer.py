"""Matplotlib chart renderer — SOTA rewrite for Phase 2 Stream D.

Public API
----------
- :func:`render_paper_figure` — render a :class:`PaperFigureSchema` (or its
  ``model_dump()`` dict) to a publication-quality PNG and return both the
  saved path and an inline-embeddable base-64 string.
- :func:`render_timeline` — retained from Phase 0 for timeline generator
  compatibility; unchanged in semantics.

Chart types supported by ``render_paper_figure``:
  ``bar``, ``line``, ``scatter``

Any other ``chart_type`` raises :class:`ValueError` immediately — no silent
fallback.

Quality defaults:
- Style: ``seaborn-v0_8-whitegrid`` (clean academic look).
- Figure size: 1200 × 800 px at 200 DPI (i.e. 6 × 4 inches @ 200 DPI).
- Axes: labelled, ticks visible, legend drawn when multiple series present.
- Caption printed as italic figure note below the chart.
- Saved with ``bbox_inches="tight"`` to avoid clipping.
"""
from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Union

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

# ---------------------------------------------------------------------------
# Style setup
# ---------------------------------------------------------------------------

_STYLE = "seaborn-v0_8-whitegrid"
# Fallback if the above is unavailable in older matplotlib
_FALLBACK_STYLE = "ggplot"

_COLORS = [
    "#2366C2",  # primary blue
    "#10B981",  # teal
    "#F59E0B",  # amber
    "#EF4444",  # red
    "#8B5CF6",  # violet
    "#06B6D4",  # cyan
    "#EC4899",  # pink
    "#F97316",  # orange
]

_DPI = 200
_FIG_W_IN = 6.0   # 1200px / 200 DPI
_FIG_H_IN = 4.0   # 800px  / 200 DPI

_SUPPORTED_CHART_TYPES = frozenset({"bar", "line", "scatter"})

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class _RenderResult(NamedTuple):
    path: Path
    png_b64: str


def _apply_style() -> None:
    try:
        plt.style.use(_STYLE)
    except OSError:
        try:
            plt.style.use(_FALLBACK_STYLE)
        except OSError:
            pass  # use matplotlib defaults


def _coerce_year(label: str) -> Optional[int]:
    match = re.search(r"(19|20)\d{2}", str(label))
    if match:
        return int(match.group(0))
    return None


def _save_figure(fig: plt.Figure, path: Path) -> str:
    """Save *fig* to *path* and return its base64-encoded PNG bytes."""
    import io
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(path), dpi=_DPI, bbox_inches="tight", format="png")
    buf = io.BytesIO()
    fig.savefig(buf, dpi=_DPI, bbox_inches="tight", format="png")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


# ---------------------------------------------------------------------------
# render_paper_figure
# ---------------------------------------------------------------------------


def render_paper_figure(
    data: Union[Dict[str, Any], Any],
    path: Path,
) -> _RenderResult:
    """Render a publication-quality chart from *data* to *path*.

    Args:
        data:  ``PaperFigureSchema.model_dump()`` dict or a Pydantic instance.
        path:  Output PNG file path.

    Returns:
        A :class:`_RenderResult` namedtuple with ``path`` and ``png_b64``
        (inline-embeddable base-64 PNG string, usable as a data URI).

    Raises:
        ValueError: If ``chart_type`` is not in ``{bar, line, scatter}``.
    """
    if not isinstance(data, dict):
        data = data.model_dump()

    chart_type: str = (data.get("chart_type") or "bar").lower()
    if chart_type not in _SUPPORTED_CHART_TYPES:
        raise ValueError(
            f"Unsupported chart_type {chart_type!r}. "
            f"Must be one of {sorted(_SUPPORTED_CHART_TYPES)}."
        )

    title: str = data.get("title", "Figure")
    x_label: str = data.get("x_label", "")
    y_label: str = data.get("y_label", "")
    caption: str = data.get("caption", "")
    series: List[Dict[str, Any]] = data.get("series") or []

    if not series:
        series = [{"name": "data", "data": []}]

    _apply_style()
    fig, ax = plt.subplots(figsize=(_FIG_W_IN, _FIG_H_IN))

    if chart_type == "bar":
        _render_bar(ax, series)
    elif chart_type == "line":
        _render_line(ax, series)
    elif chart_type == "scatter":
        _render_scatter(ax, series)

    ax.set_xlabel(x_label, fontsize=11)
    ax.set_ylabel(y_label, fontsize=11)
    ax.set_title(title, fontsize=14, fontweight="bold", pad=12)

    if len(series) > 1 or any(s.get("name") for s in series):
        ax.legend(fontsize=9, framealpha=0.8)

    if caption:
        fig.text(
            0.5,
            -0.04,
            caption,
            ha="center",
            fontsize=8,
            style="italic",
            wrap=True,
            color="#64748B",
        )

    fig.tight_layout()
    png_b64 = _save_figure(fig, Path(path))
    plt.close(fig)
    return _RenderResult(path=Path(path), png_b64=png_b64)


def _render_bar(ax: plt.Axes, series: List[Dict[str, Any]]) -> None:
    categories: List[str] = []
    for ser in series:
        for pt in ser.get("data", []):
            x = str(pt.get("x"))
            if x not in categories:
                categories.append(x)

    if not categories:
        ax.text(0.5, 0.5, "No data", ha="center", va="center",
                transform=ax.transAxes, color="#94a3b8")
        return

    indices = np.arange(len(categories))
    n = max(1, len(series))
    width = 0.8 / n

    for i, ser in enumerate(series):
        values = []
        for cat in categories:
            match = next(
                (pt for pt in ser.get("data", []) if str(pt.get("x")) == cat),
                None,
            )
            values.append(float(match["y"]) if match else 0.0)
        ax.bar(
            indices + i * width - (n - 1) * width / 2,
            values,
            width,
            label=ser.get("name", f"series{i}"),
            color=_COLORS[i % len(_COLORS)],
            alpha=0.85,
            edgecolor="white",
        )
    ax.set_xticks(indices)
    ax.set_xticklabels(categories, rotation=30 if len(categories) > 6 else 0,
                        ha="right" if len(categories) > 6 else "center",
                        fontsize=9)


def _render_line(ax: plt.Axes, series: List[Dict[str, Any]]) -> None:
    for i, ser in enumerate(series):
        pts = ser.get("data", [])
        if not pts:
            continue
        xs = [pt.get("x") for pt in pts]
        ys = [float(pt.get("y", 0)) for pt in pts]
        ax.plot(
            xs,
            ys,
            marker="o",
            markersize=5,
            linewidth=2,
            label=ser.get("name", f"series{i}"),
            color=_COLORS[i % len(_COLORS)],
        )
    ax.tick_params(axis="x", rotation=30)


def _render_scatter(ax: plt.Axes, series: List[Dict[str, Any]]) -> None:
    for i, ser in enumerate(series):
        pts = ser.get("data", [])
        if not pts:
            continue
        xs = [float(pt.get("x", 0)) for pt in pts]
        ys = [float(pt.get("y", 0)) for pt in pts]
        ax.scatter(
            xs,
            ys,
            s=60,
            alpha=0.8,
            label=ser.get("name", f"series{i}"),
            color=_COLORS[i % len(_COLORS)],
            edgecolors="white",
            linewidths=0.5,
        )


# ---------------------------------------------------------------------------
# render_timeline  (unchanged from Phase 0, retained for compatibility)
# ---------------------------------------------------------------------------


def render_timeline(data: Dict[str, Any], path: Path) -> Path:
    """Render a timeline chart from *data* to *path*.

    Retained from Phase 0 for compatibility with the timeline generator.
    """
    events = data.get("events") or []
    if not events:
        events = [{"date": "Now", "event": "No events extracted"}]

    dated: List[Dict[str, Any]] = []
    for idx, ev in enumerate(events):
        year = _coerce_year(ev.get("date", ""))
        dated.append(
            {
                "year": year if year is not None else idx,
                "label": str(ev.get("date", "")),
                "event": str(ev.get("event", "")),
            }
        )
    dated.sort(key=lambda d: d["year"])

    _apply_style()
    fig, ax = plt.subplots(figsize=(12, max(4, len(dated) * 0.6)))
    y_positions = list(range(len(dated)))

    ax.hlines(y_positions, xmin=0, xmax=[1] * len(dated),
               colors="#94a3b8", linewidth=2)
    ax.scatter([0.5] * len(dated), y_positions,
               color=_COLORS[0], s=120, zorder=3)

    for y, ev in zip(y_positions, dated):
        ax.text(0.5, y + 0.18, ev["label"],
                fontsize=10, fontweight="bold", ha="center")
        ax.text(0.52, y - 0.05,
                ev["event"][:120] + ("…" if len(ev["event"]) > 120 else ""),
                fontsize=8, ha="left", va="top", color="#334155")

    ax.set_yticks([])
    ax.set_xticks([])
    ax.set_xlim(-0.1, 2.5)
    ax.set_ylim(-1, len(dated))
    for spine in ax.spines.values():
        spine.set_visible(False)

    ax.set_title(data.get("title", "Timeline"), fontsize=14, fontweight="bold")
    fig.tight_layout()

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(path), dpi=_DPI, bbox_inches="tight")
    plt.close(fig)
    return path
