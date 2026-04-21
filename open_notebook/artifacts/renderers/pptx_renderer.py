"""python-pptx renderer for slide and pitch decks."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from pptx import Presentation
from pptx.util import Inches, Pt


def _add_title_slide(prs: Presentation, title: str, subtitle: Optional[str]) -> None:
    layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(layout)
    slide.shapes.title.text = title or "Presentation"
    placeholder = slide.placeholders[1] if len(slide.placeholders) > 1 else None
    if placeholder is not None:
        placeholder.text = subtitle or ""


def _add_content_slide(
    prs: Presentation,
    title: str,
    bullets: List[str],
    notes: Optional[str] = None,
) -> None:
    layout = prs.slide_layouts[1]
    slide = prs.slides.add_slide(layout)
    slide.shapes.title.text = title or "Slide"
    body = slide.placeholders[1].text_frame
    body.clear()
    for idx, bullet in enumerate(bullets or ["—"]):
        if idx == 0:
            body.text = str(bullet)
            paragraph = body.paragraphs[0]
        else:
            paragraph = body.add_paragraph()
            paragraph.text = str(bullet)
        for run in paragraph.runs:
            run.font.size = Pt(18)
    if notes:
        slide.notes_slide.notes_text_frame.text = str(notes)


def render_deck(
    data: Dict[str, Any],
    path: Path,
    subtitle_key: str = "subtitle",
) -> Path:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    title = data.get("title", "Presentation")
    slides = data.get("slides") or []
    if not slides:
        _add_title_slide(prs, title, data.get(subtitle_key))
    else:
        first = slides[0]
        _add_title_slide(
            prs,
            first.get("title") or title,
            data.get(subtitle_key) or (first.get("bullets") or [""])[0],
        )
        for slide in slides[1:]:
            _add_content_slide(
                prs,
                slide.get("title", ""),
                slide.get("bullets") or [],
                slide.get("notes"),
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(path))
    return path
