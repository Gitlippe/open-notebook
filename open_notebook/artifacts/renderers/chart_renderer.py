"""Matplotlib-based chart renderers (timelines, paper figures).

Publication-style defaults, grouped-bar support, series highlighting.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


_PUB_STYLE = {
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": "#333333",
    "axes.titlesize": 14,
    "axes.labelsize": 12,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
}


def _coerce_year(label: str) -> Optional[int]:
    match = re.search(r"(19|20)\d{2}", str(label))
    return int(match.group(0)) if match else None


def render_timeline(data: Dict[str, Any], path: Path) -> Path:
    events = data.get("events") or []
    if not events:
        events = [{"date": "Now", "event": "No events extracted"}]
    prepared: List[Dict[str, Any]] = []
    for idx, ev in enumerate(events):
        year = _coerce_year(ev.get("date", ""))
        prepared.append(
            {
                "sort_key": year if year is not None else idx,
                "label": str(ev.get("date", "")),
                "event": str(ev.get("event", "")),
                "importance": ev.get("importance", "major"),
                "category": ev.get("category"),
            }
        )
    prepared.sort(key=lambda d: (d["sort_key"], d["label"]))

    with plt.rc_context(_PUB_STYLE):
        fig, ax = plt.subplots(figsize=(13, max(4.5, 0.55 * len(prepared))))
        y_positions = list(range(len(prepared)))

        ax.hlines(y_positions, xmin=0, xmax=[1] * len(prepared),
                  colors="#cbd5e1", linewidth=2)

        major_color = "#2563eb"
        minor_color = "#94a3b8"
        colors = [
            major_color if p["importance"] == "major" else minor_color
            for p in prepared
        ]
        sizes = [150 if p["importance"] == "major" else 80 for p in prepared]
        ax.scatter([0.5] * len(prepared), y_positions,
                   color=colors, s=sizes, zorder=3, edgecolor="white", linewidth=1.5)

        for y, ev in zip(y_positions, prepared):
            ax.text(0.5, y + 0.22, ev["label"], fontsize=11, fontweight="bold",
                    ha="center", color="#111827")
            event_text = ev["event"]
            if len(event_text) > 140:
                event_text = event_text[:137] + "…"
            if ev.get("category"):
                event_text = f"[{ev['category']}] {event_text}"
            ax.text(0.52, y - 0.06, event_text, fontsize=9, ha="left",
                    va="top", color="#1f2937", wrap=True)

        ax.set_yticks([])
        ax.set_xticks([])
        ax.set_xlim(-0.1, 2.6)
        ax.set_ylim(-1, len(prepared))
        for spine in ax.spines.values():
            spine.set_visible(False)

        title = data.get("title", "Timeline")
        ax.set_title(title, fontsize=16, fontweight="bold", color="#0f172a", pad=14)

        path.parent.mkdir(parents=True, exist_ok=True)
        fig.tight_layout()
        fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
        plt.close(fig)
    return path


def render_paper_figure(data: Dict[str, Any], path: Path) -> Path:
    chart_type = (data.get("chart_type") or "bar").lower()
    title = data.get("title", "Figure")
    x_label = data.get("x_label", "")
    y_label = data.get("y_label", "")
    caption = data.get("caption", "")
    series = data.get("series") or []
    highlight = data.get("highlight_series")

    palette = ["#334155", "#64748b", "#94a3b8", "#cbd5e1"]
    highlight_color = "#2563eb"

    def color_for(idx: int, name: str) -> str:
        if highlight and name == highlight:
            return highlight_color
        return palette[idx % len(palette)]

    with plt.rc_context(_PUB_STYLE):
        fig, ax = plt.subplots(figsize=(8.5, 5.2))
        if not series:
            series = [{"name": "data", "data": []}]

        if chart_type in {"bar", "grouped_bar", "column"}:
            categories: List[str] = []
            for ser in series:
                for pt in ser.get("data", []):
                    x = str(pt["x"])
                    if x not in categories:
                        categories.append(x)
            indices = np.arange(len(categories))
            width = 0.8 / max(1, len(series))
            for i, ser in enumerate(series):
                values = []
                for cat in categories:
                    match = next(
                        (pt for pt in ser.get("data", []) if str(pt["x"]) == cat),
                        None,
                    )
                    values.append(float(match["y"]) if match else 0.0)
                offset = indices + i * width - (len(series) - 1) * width / 2
                bars = ax.bar(
                    offset, values, width,
                    label=ser.get("name", f"series{i}"),
                    color=color_for(i, ser.get("name", "")),
                    edgecolor="white", linewidth=0.5,
                )
                # Value labels on highlighted series
                if highlight and ser.get("name") == highlight:
                    for rect, v in zip(bars, values):
                        ax.text(
                            rect.get_x() + rect.get_width() / 2,
                            v + max(values) * 0.01,
                            f"{v:g}", ha="center", va="bottom",
                            fontsize=9, fontweight="bold", color=highlight_color,
                        )
            ax.set_xticks(indices)
            ax.set_xticklabels(categories, rotation=0)
        elif chart_type == "line":
            for i, ser in enumerate(series):
                pts = ser.get("data", [])
                xs = [pt["x"] for pt in pts]
                ys = [float(pt["y"]) for pt in pts]
                linewidth = 2.8 if ser.get("name") == highlight else 1.8
                ax.plot(xs, ys, marker="o", linewidth=linewidth,
                        label=ser.get("name", f"series{i}"),
                        color=color_for(i, ser.get("name", "")))
        elif chart_type == "scatter":
            for i, ser in enumerate(series):
                pts = ser.get("data", [])
                xs = [float(pt["x"]) for pt in pts]
                ys = [float(pt["y"]) for pt in pts]
                ax.scatter(xs, ys, s=60, alpha=0.85,
                           label=ser.get("name", f"series{i}"),
                           color=color_for(i, ser.get("name", "")))
        else:
            ax.text(0.5, 0.5, f"Unsupported chart: {chart_type}",
                    ha="center", va="center", transform=ax.transAxes)

        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.set_title(title, fontsize=14, fontweight="bold", color="#0f172a", pad=12)
        if any(ser.get("name") for ser in series):
            ax.legend(frameon=False, loc="best")
        ax.yaxis.grid(True, linestyle="--", alpha=0.35)
        ax.set_axisbelow(True)

        if caption:
            fig.text(0.5, -0.06, caption, ha="center", fontsize=9,
                     style="italic", color="#475569", wrap=True)

        path.parent.mkdir(parents=True, exist_ok=True)
        fig.tight_layout()
        fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
        plt.close(fig)
    return path
