"""Matplotlib-based chart renderers (timelines, paper figures)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402


def _coerce_year(label: str) -> Optional[int]:
    match = re.search(r"(19|20)\d{2}", str(label))
    if match:
        return int(match.group(0))
    return None


def render_timeline(data: Dict[str, Any], path: Path) -> Path:
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

    fig, ax = plt.subplots(figsize=(12, max(4, len(dated) * 0.5)))
    y_positions = list(range(len(dated)))

    ax.hlines(
        y_positions,
        xmin=0,
        xmax=[1] * len(dated),
        colors="#94a3b8",
        linewidth=2,
    )
    ax.scatter([0.5] * len(dated), y_positions, color="#2563eb", s=120, zorder=3)

    for y, ev in zip(y_positions, dated):
        ax.text(
            0.5,
            y + 0.15,
            ev["label"],
            fontsize=10,
            fontweight="bold",
            ha="center",
        )
        ax.text(
            0.52,
            y - 0.05,
            ev["event"][:120] + ("…" if len(ev["event"]) > 120 else ""),
            fontsize=8,
            ha="left",
            va="top",
        )

    ax.set_yticks([])
    ax.set_xticks([])
    ax.set_xlim(-0.1, 2.5)
    ax.set_ylim(-1, len(dated))
    for spine in ax.spines.values():
        spine.set_visible(False)

    title = data.get("title", "Timeline")
    ax.set_title(title, fontsize=14, fontweight="bold")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def render_paper_figure(data: Dict[str, Any], path: Path) -> Path:
    chart_type = (data.get("chart_type") or "bar").lower()
    title = data.get("title", "Figure")
    x_label = data.get("x_label", "")
    y_label = data.get("y_label", "")
    caption = data.get("caption", "")
    series = data.get("series") or []

    fig, ax = plt.subplots(figsize=(8, 5))

    colors = ["#2563eb", "#16a34a", "#dc2626", "#f59e0b", "#a855f7"]
    if not series:
        series = [{"name": "data", "data": []}]

    if chart_type in {"bar", "column"}:
        categories: List[str] = []
        for ser in series:
            for pt in ser.get("data", []):
                x = str(pt.get("x"))
                if x not in categories:
                    categories.append(x)
        import numpy as np

        indices = np.arange(len(categories))
        width = 0.8 / max(1, len(series))
        for i, ser in enumerate(series):
            values = []
            for cat in categories:
                match = next(
                    (pt for pt in ser.get("data", []) if str(pt.get("x")) == cat),
                    None,
                )
                values.append(float(match["y"]) if match else 0.0)
            ax.bar(
                indices + i * width - (len(series) - 1) * width / 2,
                values,
                width,
                label=ser.get("name", f"series{i}"),
                color=colors[i % len(colors)],
            )
        ax.set_xticks(indices)
        ax.set_xticklabels(categories)
    elif chart_type == "line":
        for i, ser in enumerate(series):
            pts = ser.get("data", [])
            xs = [pt.get("x") for pt in pts]
            ys = [float(pt.get("y", 0)) for pt in pts]
            ax.plot(xs, ys, marker="o", label=ser.get("name", f"series{i}"),
                    color=colors[i % len(colors)])
    elif chart_type == "scatter":
        for i, ser in enumerate(series):
            pts = ser.get("data", [])
            xs = [float(pt.get("x", 0)) for pt in pts]
            ys = [float(pt.get("y", 0)) for pt in pts]
            ax.scatter(xs, ys, label=ser.get("name", f"series{i}"),
                       color=colors[i % len(colors)])
    else:
        ax.text(0.5, 0.5, f"Unsupported chart: {chart_type}",
                ha="center", va="center", transform=ax.transAxes)

    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    ax.set_title(title, fontsize=13, fontweight="bold")
    if any(ser.get("name") for ser in series):
        ax.legend()
    ax.grid(True, alpha=0.3)

    if caption:
        fig.text(0.5, -0.02, caption, ha="center", fontsize=8, style="italic", wrap=True)

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path
