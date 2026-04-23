"""Matplotlib chart renderer — publication-quality rewrite.

Public API
----------
- :func:`render_paper_figure` — render a :class:`PaperFigureSchema` (or its
  ``model_dump()`` dict) to a PNG and return both the saved path and an
  inline-embeddable base-64 string.
- :func:`render_timeline` — renders a dated timeline (used by the timeline
  generator).

Chart types supported by ``render_paper_figure``: ``bar``, ``line``, ``scatter``.

Any other ``chart_type`` raises :class:`ValueError` immediately — no silent
fallback.

Layout philosophy
-----------------
Paper-grade charts need to handle a lot of variability (1–12 categories,
labels ranging from 3 to 40 chars, 1–6 series, captions of 1–6 lines) without
letting the LLM's schema "fight" matplotlib's layout. Concretely:

* **Width grows with category count** so bars never crush together.
* **Height grows with caption line count + label rotation** so nothing
  overlaps the x-axis tick labels.
* **Long category labels auto-wrap** to at most 2 lines at a safe character
  width.
* **Legend is placed outside the plot** (below the title, horizontal) when it
  would otherwise collide with the top-right bars.
* **Caption is rendered inside the axes figure area** with reserved margin via
  ``subplots_adjust`` so ``bbox_inches="tight"`` cannot crop it into the axes.
"""
from __future__ import annotations

import base64
import re
import textwrap
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

_DPI = 180
_MIN_W_IN = 9.0   # baseline width — big enough for readable labels
_MIN_H_IN = 6.0   # baseline height — room for caption + legend
_MAX_W_IN = 18.0
_MAX_H_IN = 12.0

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
            pass
    # Fine-tune defaults regardless of style.
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 11,
            "axes.titlesize": 15,
            "axes.titleweight": "bold",
            "axes.titlepad": 14,
            "axes.labelsize": 12,
            "axes.labelweight": "semibold",
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
            "legend.frameon": True,
            "legend.framealpha": 0.92,
            "legend.edgecolor": "#CBD5E1",
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#64748B",
            "axes.linewidth": 0.9,
            "axes.grid": True,
            "grid.color": "#E2E8F0",
            "grid.linewidth": 0.8,
            "grid.linestyle": "--",
        }
    )


def _coerce_year(label: str) -> Optional[int]:
    match = re.search(r"(19|20)\d{2}", str(label))
    if match:
        return int(match.group(0))
    return None


def _wrap_label(label: str, max_chars: int = 18) -> str:
    """Wrap a long category label to at most 2 lines of ~max_chars each."""
    s = str(label).strip()
    if len(s) <= max_chars:
        return s
    lines = textwrap.wrap(s, width=max_chars, break_long_words=False, max_lines=2, placeholder="…")
    return "\n".join(lines)


def _choose_figsize(
    n_categories: int,
    n_series: int,
    max_label_len: int,
    caption_lines: int,
    legend_slot: bool,
) -> tuple[float, float]:
    """Pick width/height that leave room for labels + caption + legend.

    The width formula budgets ~0.9in per category plus extra space when
    labels are long (each char beyond 10 adds width) and when there are
    multiple series (each series widens the bar group). This stops tick
    labels from crashing into each other.
    """
    # Per-category slot: larger for longer labels + multiple series.
    per_cat = 0.90
    per_cat += max(0, max_label_len - 10) * 0.05
    per_cat += max(0, n_series - 1) * 0.15
    w = 2.0 + n_categories * per_cat
    # Height grows with caption and rotated labels.
    h = _MIN_H_IN + caption_lines * 0.32
    if legend_slot:
        h += 0.6
    if max_label_len > 18:
        h += 1.0
    elif max_label_len > 10:
        h += 0.5
    return (max(_MIN_W_IN, min(_MAX_W_IN, w)), min(_MAX_H_IN, h))


def _save_figure(fig: plt.Figure, path: Path) -> str:
    """Save *fig* to *path* and return its base64-encoded PNG bytes."""
    import io

    path.parent.mkdir(parents=True, exist_ok=True)
    # Do NOT use bbox_inches="tight" — it crops the reserved caption strip.
    # We rely on subplots_adjust() to size things correctly.
    fig.savefig(str(path), dpi=_DPI, format="png", facecolor="white")
    buf = io.BytesIO()
    fig.savefig(buf, dpi=_DPI, format="png", facecolor="white")
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
        A :class:`_RenderResult` namedtuple with ``path`` and ``png_b64``.

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
    caption: str = data.get("caption", "") or ""
    series: List[Dict[str, Any]] = data.get("series") or []
    if not series:
        series = [{"name": "data", "data": []}]

    # --- pre-compute layout knobs --------------------------------------
    # Pull category strings to estimate width / label-wrap needs.
    cats: list[str] = []
    for ser in series:
        for pt in ser.get("data", []):
            cats.append(str(pt.get("x", "")))

    max_label_len = max((len(c) for c in cats), default=0)
    n_cats = len({c for c in cats}) or 1
    # Caption wraps to ~120 chars per line for layout budget.
    caption_lines = len(textwrap.wrap(caption, width=120)) if caption else 0
    legend_slot = len(series) > 1 or any(s.get("name") for s in series)

    fig_w, fig_h = _choose_figsize(
        n_categories=n_cats,
        n_series=len(series),
        max_label_len=max_label_len,
        caption_lines=caption_lines,
        legend_slot=legend_slot,
    )

    _apply_style()
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    orientation: str = "vertical"
    if chart_type == "bar":
        orientation = _render_bar(ax, series, max_label_len=max_label_len)  # type: ignore[assignment]
    elif chart_type == "line":
        _render_line(ax, series)
    elif chart_type == "scatter":
        _render_scatter(ax, series)

    # Title (wrap if long).
    ax.set_title(textwrap.fill(str(title), width=70), loc="left")
    # When we flipped to horizontal bars, swap axis labels so they describe the
    # right axes.
    if orientation == "horizontal":
        ax.set_xlabel(y_label)
        ax.set_ylabel(x_label)
    else:
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)

    # Legend ABOVE the axes, horizontal, so it never collides with bars.
    if legend_slot:
        handles, labels = ax.get_legend_handles_labels()
        if handles:
            fig.legend(
                handles,
                labels,
                loc="upper center",
                bbox_to_anchor=(0.5, 0.995),
                ncol=min(len(handles), 4),
                frameon=False,
                fontsize=10,
            )

    # Reserve margins by orientation.
    if orientation == "horizontal":
        # Horizontal bars need extra left margin for long category labels,
        # not extra bottom margin.
        left_margin = 0.08 + min(0.22, 0.008 * max_label_len)
        bottom_margin = 0.10 + 0.05 * caption_lines
    else:
        left_margin = 0.10
        bottom_margin = 0.18
        if max_label_len > 10:
            bottom_margin += 0.08
        if max_label_len > 18:
            bottom_margin += 0.08
        if caption_lines:
            bottom_margin += 0.05 * caption_lines

    top_margin = 0.88 if legend_slot else 0.92
    fig.subplots_adjust(
        left=left_margin,
        right=0.97,
        top=top_margin,
        bottom=min(0.45, bottom_margin),
    )

    # Caption sits in the reserved bottom strip. Use figure coordinates so
    # it isn't clipped by the axes.
    if caption:
        wrapped = "\n".join(textwrap.wrap(caption, width=120))
        fig.text(
            0.5,
            0.02,
            wrapped,
            ha="center",
            va="bottom",
            fontsize=9,
            style="italic",
            color="#475569",
        )

    png_b64 = _save_figure(fig, Path(path))
    plt.close(fig)
    return _RenderResult(path=Path(path), png_b64=png_b64)


def _render_bar(
    ax: plt.Axes,
    series: List[Dict[str, Any]],
    *,
    max_label_len: int,
) -> "BarOrientation":
    """Render a grouped bar chart.

    When category labels are too long to sit comfortably along the x-axis
    (long labels × many categories), auto-flip to horizontal bars so labels
    read naturally along the y-axis without rotation. Returns the orientation
    used so the caller can adjust axis labels accordingly.
    """
    categories: List[str] = []
    for ser in series:
        for pt in ser.get("data", []):
            x = str(pt.get("x"))
            if x not in categories:
                categories.append(x)

    if not categories:
        ax.text(
            0.5, 0.5, "No data", ha="center", va="center",
            transform=ax.transAxes, color="#94a3b8", fontsize=12,
        )
        return "vertical"  # type: ignore[return-value]

    # Auto-orientation: horizontal bars when labels dominate (>= 14 chars AND
    # >= 6 categories). Horizontal layout lets labels breathe.
    use_horizontal = max_label_len >= 14 and len(categories) >= 6

    indices = np.arange(len(categories))
    n = max(1, len(series))
    width = min(0.8 / n, 0.38)

    for i, ser in enumerate(series):
        values = []
        for cat in categories:
            match = next(
                (pt for pt in ser.get("data", []) if str(pt.get("x")) == cat),
                None,
            )
            values.append(float(match["y"]) if match else 0.0)
        offset = i * width - (n - 1) * width / 2
        color = _COLORS[i % len(_COLORS)]
        label = ser.get("name", f"series{i}")
        if use_horizontal:
            ax.barh(
                indices + offset,
                values,
                width,
                label=label,
                color=color,
                alpha=0.92,
                edgecolor="white",
                linewidth=1.2,
            )
        else:
            ax.bar(
                indices + offset,
                values,
                width,
                label=label,
                color=color,
                alpha=0.92,
                edgecolor="white",
                linewidth=1.2,
            )

    if use_horizontal:
        ax.set_yticks(indices)
        wrapped = [_wrap_label(c, max_chars=30) for c in categories]
        ax.set_yticklabels(wrapped, fontsize=10)
        ax.invert_yaxis()  # first category at the top (reads top-to-bottom)
        ax.xaxis.grid(True)
        ax.yaxis.grid(False)
        return "horizontal"  # type: ignore[return-value]

    # Vertical path: wrap labels, pick rotation, anchor.
    ax.set_xticks(indices)
    wrapped_labels = [_wrap_label(c, max_chars=18) for c in categories]
    if max_label_len <= 8 and len(categories) <= 6:
        rotation, ha = 0, "center"
    elif max_label_len <= 13:
        rotation, ha = 30, "right"
    else:
        rotation, ha = 45, "right"
    ax.set_xticklabels(wrapped_labels, rotation=rotation, ha=ha)
    if rotation:
        for tick in ax.get_xticklabels():
            tick.set_rotation_mode("anchor")
    ax.yaxis.grid(True)
    ax.xaxis.grid(False)
    return "vertical"  # type: ignore[return-value]


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
            markersize=6,
            linewidth=2.2,
            label=ser.get("name", f"series{i}"),
            color=_COLORS[i % len(_COLORS)],
        )
    # If x values look categorical/long, rotate.
    xs_sample = [pt.get("x") for ser in series for pt in ser.get("data", [])[:1]]
    longest = max((len(str(x)) for x in xs_sample), default=0)
    if longest > 10:
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
            s=80,
            alpha=0.85,
            label=ser.get("name", f"series{i}"),
            color=_COLORS[i % len(_COLORS)],
            edgecolors="white",
            linewidths=0.8,
        )


# ---------------------------------------------------------------------------
# render_timeline  (unchanged from Phase 0 modulo the new DPI default)
# ---------------------------------------------------------------------------


def render_timeline(data: Dict[str, Any], path: Path) -> Path:
    """Render a timeline as a styled vertical journey.

    Two layout modes:

    * **Chronological** (>=60% of events have a parseable year) — plot events
      on a real horizontal date axis so spacing reflects time.
    * **Phase list** (otherwise) — render as a clean vertical journey with a
      left-rail spine, coloured markers, and full event text on the right.
      Looks like a product-roadmap card, not a fake horizontal bar.

    Long event text wraps to ~80 chars across up to 3 lines (no mid-word
    truncation). Height grows with the number of events so entries never
    overlap each other.
    """
    events = data.get("events") or []
    if not events:
        events = [{"date": "Now", "event": "No events extracted"}]

    parsed: List[Dict[str, Any]] = []
    for idx, ev in enumerate(events):
        year = _coerce_year(ev.get("date", ""))
        parsed.append(
            {
                "year": year,
                "label": str(ev.get("date", "")).strip() or f"Event {idx + 1}",
                "event": str(ev.get("event", "")).strip(),
            }
        )
    has_years = sum(1 for p in parsed if p["year"] is not None) >= max(
        2, int(len(parsed) * 0.6)
    )

    _apply_style()

    if has_years:
        return _render_chronological_timeline(parsed, data.get("title", "Timeline"), Path(path))
    return _render_phase_timeline(parsed, data.get("title", "Timeline"), Path(path))


def _render_chronological_timeline(parsed: List[Dict[str, Any]], title: str, path: Path) -> Path:
    """Standard timeline: real x-axis, events offset vertically to avoid overlap."""
    parsed.sort(key=lambda p: (p["year"] or 0))
    years = [p["year"] if p["year"] is not None else i for i, p in enumerate(parsed)]

    n = len(parsed)
    fig_w = max(13.0, 10 + 0.5 * n)
    fig_h = max(6.0, 5 + 0.6 * n)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    # Baseline arrow
    ax.axhline(0, color="#cbd5e1", linewidth=1.2, zorder=1)

    # Stagger y-positions so labels don't collide (odd-above, even-below)
    for i, (year, ev) in enumerate(zip(years, parsed)):
        y = 0.8 if i % 2 == 0 else -0.8
        color = _COLORS[i % len(_COLORS)]
        ax.scatter([year], [0], color=color, s=180, zorder=3, edgecolors="white", linewidths=1.5)
        ax.plot([year, year], [0, y * 0.6], color=color, linewidth=1.2, zorder=2)
        wrapped = "\n".join(textwrap.wrap(ev["event"], width=42, max_lines=3, placeholder="…"))
        ax.text(
            year,
            y,
            f"{ev['label']}\n" + wrapped if ev["label"] != str(year) else wrapped,
            fontsize=9,
            ha="center",
            va="bottom" if y > 0 else "top",
            color="#0f172a",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="white", edgecolor=color, linewidth=1.0),
        )

    ax.set_title(title, loc="left", pad=14)
    ax.set_yticks([])
    ax.set_ylim(-2.0, 2.0)
    ax.set_xlim(min(years) - 0.5, max(years) + 0.5)
    for spine in ("left", "right", "top"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#94a3b8")

    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(path), dpi=_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def _render_phase_timeline(parsed: List[Dict[str, Any]], title: str, path: Path) -> Path:
    """Vertical-journey layout for non-year labels (phases, stages, etc.)."""
    n = len(parsed)
    # Height grows with count. ~0.9in per event gives room for wrapped text.
    fig_h = max(5.0, 1.5 + n * 0.9)
    fig_w = 12.0
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    # Left rail position (in axes coords).
    RAIL_X = 0.10
    LABEL_X = 0.16  # where phase label starts
    EVENT_X = 0.16  # where event text starts (below label)

    # Draw the vertical rail.
    ax.plot([RAIL_X, RAIL_X], [0, 1], color="#cbd5e1", linewidth=2.5, transform=ax.transAxes, zorder=1)

    # Place events top-to-bottom evenly.
    for i, ev in enumerate(parsed):
        # y in axes coords: 1.0 at top, 0.0 at bottom; give each event a slot.
        slot_top = 1.0 - (i / n)
        slot_mid = slot_top - 0.5 / n
        color = _COLORS[i % len(_COLORS)]

        # Marker dot on the rail
        ax.scatter(
            [RAIL_X], [slot_mid],
            s=260, color=color, zorder=3,
            edgecolors="white", linewidths=2.0,
            transform=ax.transAxes,
        )
        # Small connector line from the rail to the label area
        ax.plot(
            [RAIL_X, LABEL_X - 0.005], [slot_mid, slot_mid],
            color=color, linewidth=1.5, alpha=0.5,
            transform=ax.transAxes, zorder=2,
        )

        # Phase label (bold)
        ax.text(
            LABEL_X, slot_mid + 0.025,
            ev["label"],
            fontsize=12, fontweight="bold", color="#0f172a",
            transform=ax.transAxes, ha="left", va="bottom",
        )
        # Event text (wrapped)
        wrapped = "\n".join(textwrap.wrap(ev["event"], width=90, max_lines=3, placeholder="…"))
        ax.text(
            EVENT_X, slot_mid - 0.01,
            wrapped,
            fontsize=10, color="#334155",
            transform=ax.transAxes, ha="left", va="top",
        )

    # Hide default axes
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title(title, loc="left", pad=16, fontsize=15, fontweight="bold")

    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(path), dpi=_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path
