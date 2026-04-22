"""Pillow-based renderer for infographics.

Produces a clean, modern portrait infographic PNG from a structured spec.
Supports ``Infographic`` schema fields: title, subtitle, lede, stats (with
optional caveat), sections (with icon_hint), takeaway, color_theme.
"""
from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageDraw, ImageFont

_THEMES = {
    "blue":   {"bg": "#0f172a", "panel": "#1e293b", "accent": "#38bdf8",
               "text": "#f1f5f9", "muted": "#94a3b8", "band": "#0ea5e9"},
    "green":  {"bg": "#052e16", "panel": "#064e3b", "accent": "#4ade80",
               "text": "#ecfdf5", "muted": "#86efac", "band": "#16a34a"},
    "orange": {"bg": "#431407", "panel": "#7c2d12", "accent": "#fb923c",
               "text": "#fff7ed", "muted": "#fdba74", "band": "#ea580c"},
    "mono":   {"bg": "#111827", "panel": "#1f2937", "accent": "#f3f4f6",
               "text": "#f9fafb", "muted": "#9ca3af", "band": "#374151"},
    "violet": {"bg": "#1e1b4b", "panel": "#312e81", "accent": "#a78bfa",
               "text": "#ede9fe", "muted": "#c4b5fd", "band": "#7c3aed"},
}

_ICONS = {
    "chart": "◧",
    "shield": "⛨",
    "clock": "◴",
    "people": "⚇",
    "spark": "✦",
    "flag": "⚑",
    "lightning": "⚡",
    "globe": "◉",
    "check": "✓",
    "arrow": "→",
}


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates_bold = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    candidates_regular = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    paths = candidates_bold if bold else candidates_regular
    for p in paths:
        try:
            return ImageFont.truetype(p, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font) -> Tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _wrap(text: str, width: int) -> List[str]:
    return textwrap.wrap(text, width=width) or [""]


def render_infographic(data: Dict[str, Any], path: Path) -> Path:
    theme = _THEMES.get((data.get("color_theme") or "blue").lower(), _THEMES["blue"])

    W, H = 1200, 1800
    img = Image.new("RGB", (W, H), theme["bg"])
    draw = ImageDraw.Draw(img)

    padding = 60
    y = padding

    # Top accent band
    draw.rectangle([(0, 0), (W, 12)], fill=theme["accent"])

    title_font = _font(58, bold=True)
    subtitle_font = _font(26)
    lede_font = _font(24, bold=True)
    h_font = _font(30, bold=True)
    body_font = _font(22)
    stat_num_font = _font(56, bold=True)
    stat_label_font = _font(20)
    caveat_font = _font(16)
    takeaway_font = _font(24, bold=True)

    # Title
    for line in _wrap(data.get("title", "Infographic"), 30):
        draw.text((padding, y), line, font=title_font, fill=theme["accent"])
        _, h = _text_size(draw, line, title_font)
        y += h + 6
    y += 12

    # Subtitle
    subtitle = data.get("subtitle", "")
    if subtitle:
        for line in _wrap(subtitle, 60):
            draw.text((padding, y), line, font=subtitle_font, fill=theme["muted"])
            _, h = _text_size(draw, line, subtitle_font)
            y += h + 4
        y += 10

    # Divider
    draw.rectangle([(padding, y), (W - padding, y + 3)], fill=theme["accent"])
    y += 24

    # Lede panel
    lede = data.get("lede", "")
    if lede:
        lede_top = y
        lede_lines = _wrap(lede, 58)
        lede_h = 36 + 30 * len(lede_lines)
        draw.rectangle(
            [(padding, lede_top), (W - padding, lede_top + lede_h)],
            fill=theme["panel"],
        )
        # Left accent strip
        draw.rectangle(
            [(padding, lede_top), (padding + 8, lede_top + lede_h)],
            fill=theme["accent"],
        )
        ty = lede_top + 18
        for line in lede_lines:
            draw.text((padding + 24, ty), line, font=lede_font, fill=theme["text"])
            _, lh = _text_size(draw, line, lede_font)
            ty += lh + 6
        y = lede_top + lede_h + 32

    # Stats panel
    stats = data.get("stats", []) or []
    if stats:
        panel_h = 200
        draw.rectangle(
            [(padding, y), (W - padding, y + panel_h)], fill=theme["panel"],
        )
        cols = min(len(stats), 4)
        col_w = (W - 2 * padding) // cols
        for i, st in enumerate(stats[:cols]):
            cx = padding + i * col_w + col_w // 2
            value = str(st.get("value", ""))
            label = str(st.get("label", ""))
            caveat = str(st.get("caveat") or "")
            v_w, v_h = _text_size(draw, value, stat_num_font)
            draw.text((cx - v_w // 2, y + 30), value, font=stat_num_font,
                      fill=theme["accent"])
            # Separator line between cols
            if i > 0:
                x_sep = padding + i * col_w
                draw.rectangle(
                    [(x_sep, y + 30), (x_sep + 1, y + panel_h - 20)],
                    fill=theme["muted"],
                )
            for li, ln in enumerate(_wrap(label, 18)[:2]):
                l_w, l_h = _text_size(draw, ln, stat_label_font)
                draw.text(
                    (cx - l_w // 2, y + 30 + v_h + 12 + li * (l_h + 2)),
                    ln, font=stat_label_font, fill=theme["text"],
                )
            if caveat:
                c_lines = _wrap(caveat, 24)[:2]
                cy = y + panel_h - 32 - len(c_lines) * 18
                for ln in c_lines:
                    c_w, _ = _text_size(draw, ln, caveat_font)
                    draw.text(
                        (cx - c_w // 2, cy),
                        ln, font=caveat_font, fill=theme["muted"],
                    )
                    cy += 18
        y += panel_h + 32

    # Sections
    for sect in (data.get("sections") or [])[:6]:
        heading = sect.get("heading", "")
        body = sect.get("text", "")
        icon_hint = (sect.get("icon_hint") or "arrow").lower()
        icon_char = _ICONS.get(icon_hint, _ICONS["arrow"])
        # Heading row: icon + heading
        draw.text((padding, y), icon_char, font=h_font, fill=theme["accent"])
        draw.text((padding + 44, y), heading, font=h_font, fill=theme["accent"])
        _, h = _text_size(draw, heading, h_font)
        y += h + 10
        for line in _wrap(body, 72):
            if y + 32 > H - padding - 100:
                break
            draw.text((padding, y), line, font=body_font, fill=theme["text"])
            _, lh = _text_size(draw, line, body_font)
            y += lh + 4
        y += 22
        if y > H - padding - 120:
            break

    # Takeaway banner
    takeaway = data.get("takeaway", "")
    if takeaway:
        band_top = H - 120
        draw.rectangle([(0, band_top), (W, H)], fill=theme["band"])
        for idx, line in enumerate(_wrap(takeaway, 70)[:2]):
            tw, th = _text_size(draw, line, takeaway_font)
            draw.text(
                ((W - tw) // 2, band_top + 24 + idx * (th + 4)),
                line, font=takeaway_font, fill="#ffffff",
            )

    # Footer
    footer = "Generated by Open Notebook"
    f_w, f_h = _text_size(draw, footer, stat_label_font)
    draw.text((W - padding - f_w, H - 20 - f_h), footer,
              font=stat_label_font, fill="#ffffff")

    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(path), format="PNG")
    return path


def render_infographic_html(data: Dict[str, Any], path: Path) -> Path:
    theme = (data.get("color_theme") or "blue").lower()
    bg = _THEMES.get(theme, _THEMES["blue"])
    sections = data.get("sections") or []
    stats = data.get("stats") or []

    sections_html = "\n".join(
        f"<section><h2>{s.get('heading', '')}</h2>"
        f"<p>{s.get('text', '')}</p></section>"
        for s in sections
    )
    stats_html = "\n".join(
        f'<div class="stat"><div class="num">{s.get("value", "")}</div>'
        f'<div class="lbl">{s.get("label", "")}</div>'
        + (f'<div class="caveat">{s["caveat"]}</div>' if s.get("caveat") else "")
        + "</div>"
        for s in stats
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"><title>{data.get('title', 'Infographic')}</title>
<style>
  body {{ background: {bg['bg']}; color: {bg['text']}; font-family:
         -apple-system, system-ui, 'Segoe UI', sans-serif; padding: 48px; }}
  h1 {{ color: {bg['accent']}; font-size: 48px; margin: 0 0 12px; }}
  .lede {{ background: {bg['panel']}; border-left: 6px solid {bg['accent']};
         padding: 18px 24px; font-size: 20px; font-weight: 600; border-radius: 8px; }}
  h2 {{ color: {bg['accent']}; margin-top: 32px; }}
  .stats {{ display: flex; gap: 24px; background: {bg['panel']}; padding: 24px;
           border-radius: 16px; margin: 24px 0; }}
  .stat {{ flex: 1; text-align: center; }}
  .num {{ font-size: 42px; font-weight: 700; color: {bg['accent']}; }}
  .lbl {{ color: {bg['text']}; margin-top: 4px; font-weight: 600; }}
  .caveat {{ color: {bg['muted']}; margin-top: 6px; font-size: 12px; }}
  section {{ background: {bg['panel']}; padding: 16px 24px; border-radius: 12px;
             margin: 16px 0; }}
  .takeaway {{ background: {bg['band']}; color: white; padding: 18px;
               border-radius: 12px; margin-top: 40px; font-size: 20px;
               font-weight: 700; text-align: center; }}
</style>
</head>
<body>
<h1>{data.get('title', 'Infographic')}</h1>
<p style="color:{bg['muted']}">{data.get('subtitle', '')}</p>
<div class="lede">{data.get('lede', '')}</div>
<div class="stats">{stats_html}</div>
{sections_html}
<div class="takeaway">{data.get('takeaway', '')}</div>
<footer style="margin-top:48px;color:{bg['muted']};font-size:12px;">Generated by Open Notebook</footer>
</body></html>"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path
