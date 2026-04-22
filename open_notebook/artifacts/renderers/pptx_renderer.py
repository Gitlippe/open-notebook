"""python-pptx renderer for slide and pitch decks.

Supports the richer :class:`SlideDeck` / :class:`PitchDeck` schemas by
reading the ``slide_type`` field (title / agenda / section / content /
stat / quote / closing) and picking an appropriate layout and visual
treatment for each.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Emu, Inches, Pt

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)

_ACCENT = RGBColor(0x2E, 0x7D, 0xFF)
_DARK = RGBColor(0x0F, 0x17, 0x2A)
_MUTED = RGBColor(0x64, 0x74, 0x8B)
_LIGHT = RGBColor(0xF1, 0xF5, 0xF9)


def _add_background(slide, color: RGBColor) -> None:
    bg = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, SLIDE_H
    )
    bg.fill.solid()
    bg.fill.fore_color.rgb = color
    bg.line.fill.background()
    bg.shadow.inherit = False
    slide.shapes._spTree.remove(bg._element)
    slide.shapes._spTree.insert(2, bg._element)


def _accent_stripe(slide) -> None:
    stripe = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, Inches(0.2)
    )
    stripe.fill.solid()
    stripe.fill.fore_color.rgb = _ACCENT
    stripe.line.fill.background()


def _title_slide(prs, title: str, subtitle: Optional[str]) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    _add_background(slide, _DARK)
    _accent_stripe(slide)

    title_box = slide.shapes.add_textbox(
        Inches(0.8), Inches(2.8), Inches(12), Inches(1.7)
    )
    tf = title_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title or "Presentation"
    run = p.runs[0]
    run.font.size = Pt(46)
    run.font.bold = True
    run.font.color.rgb = _ACCENT

    if subtitle:
        sub_box = slide.shapes.add_textbox(
            Inches(0.8), Inches(4.6), Inches(12), Inches(1.2)
        )
        stf = sub_box.text_frame
        stf.word_wrap = True
        sp = stf.paragraphs[0]
        sp.text = subtitle
        srun = sp.runs[0]
        srun.font.size = Pt(22)
        srun.font.color.rgb = _LIGHT


def _agenda_slide(prs, title: str, bullets: List[str]) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_background(slide, _LIGHT)
    _accent_stripe(slide)
    _header(slide, title)
    box = slide.shapes.add_textbox(
        Inches(0.8), Inches(1.8), Inches(12), Inches(5)
    )
    tf = box.text_frame
    tf.word_wrap = True
    for i, b in enumerate(bullets or ["—"]):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = f"{i + 1:>2}.  {b}"
        for run in p.runs:
            run.font.size = Pt(28)
            run.font.color.rgb = _DARK
            run.font.bold = True


def _content_slide(
    prs, title: str, bullets: List[str], notes: Optional[str]
) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_background(slide, _LIGHT)
    _accent_stripe(slide)
    _header(slide, title)
    box = slide.shapes.add_textbox(
        Inches(0.8), Inches(1.7), Inches(12), Inches(5.2)
    )
    tf = box.text_frame
    tf.word_wrap = True
    for i, b in enumerate(bullets or ["—"]):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = b
        p.level = 0
        for run in p.runs:
            run.font.size = Pt(22)
            run.font.color.rgb = _DARK
    _set_notes(slide, notes)


def _section_slide(prs, title: str) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_background(slide, _ACCENT)
    box = slide.shapes.add_textbox(
        Inches(0.8), Inches(3.0), Inches(12), Inches(1.5)
    )
    p = box.text_frame.paragraphs[0]
    p.text = title
    run = p.runs[0]
    run.font.size = Pt(48)
    run.font.bold = True
    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)


def _stat_slide(prs, title: str, bullets: List[str], notes: Optional[str]) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_background(slide, _DARK)
    _accent_stripe(slide)
    _header(slide, title, color=_LIGHT)
    # Highlight first bullet as the big stat, remaining as supporting text.
    headline = bullets[0] if bullets else ""
    rest = bullets[1:] if len(bullets) > 1 else []
    headline_box = slide.shapes.add_textbox(
        Inches(0.8), Inches(2.4), Inches(12), Inches(2.2)
    )
    tf = headline_box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = headline
    run = p.runs[0]
    run.font.size = Pt(44)
    run.font.bold = True
    run.font.color.rgb = _ACCENT

    if rest:
        rest_box = slide.shapes.add_textbox(
            Inches(0.8), Inches(5.0), Inches(12), Inches(2.0)
        )
        rf = rest_box.text_frame
        rf.word_wrap = True
        for i, b in enumerate(rest):
            pp = rf.paragraphs[0] if i == 0 else rf.add_paragraph()
            pp.text = "• " + b
            for run in pp.runs:
                run.font.size = Pt(22)
                run.font.color.rgb = _LIGHT
    _set_notes(slide, notes)


def _closing_slide(prs, title: str, bullets: List[str], notes: Optional[str]) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_background(slide, _DARK)
    _accent_stripe(slide)
    box = slide.shapes.add_textbox(
        Inches(0.8), Inches(2.5), Inches(12), Inches(3)
    )
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    run = p.runs[0]
    run.font.size = Pt(40)
    run.font.bold = True
    run.font.color.rgb = _ACCENT
    for i, b in enumerate(bullets or []):
        if i == 0 and p.text == title:
            pp = tf.add_paragraph()
        else:
            pp = tf.add_paragraph()
        pp.text = b
        for run in pp.runs:
            run.font.size = Pt(22)
            run.font.color.rgb = _LIGHT
    _set_notes(slide, notes)


def _header(slide, title: str, color: RGBColor = _DARK) -> None:
    box = slide.shapes.add_textbox(
        Inches(0.8), Inches(0.5), Inches(12), Inches(0.9)
    )
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title or ""
    run = p.runs[0]
    run.font.size = Pt(32)
    run.font.bold = True
    run.font.color.rgb = color


def _set_notes(slide, notes: Optional[str]) -> None:
    if notes:
        slide.notes_slide.notes_text_frame.text = notes


def render_deck(
    data: Dict[str, Any],
    path: Path,
    subtitle_key: str = "subtitle",
) -> Path:
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    title = data.get("title", "Presentation")
    subtitle = data.get(subtitle_key) or data.get("tagline") or ""
    slides = data.get("slides") or []

    if not slides:
        _title_slide(prs, title, subtitle)
    else:
        first_has_title = any(s.get("slide_type") == "title" for s in slides)
        if not first_has_title:
            _title_slide(prs, title, subtitle)

        for slide in slides:
            slide_type = slide.get("slide_type", "content")
            st_title = slide.get("title", "")
            bullets = slide.get("bullets") or []
            notes = slide.get("notes")
            if slide_type == "title":
                _title_slide(prs, st_title or title, subtitle)
            elif slide_type == "agenda":
                _agenda_slide(prs, st_title or "Agenda", bullets)
            elif slide_type == "section":
                _section_slide(prs, st_title)
            elif slide_type == "stat":
                _stat_slide(prs, st_title, bullets, notes)
            elif slide_type == "closing":
                _closing_slide(prs, st_title or "Thank you", bullets, notes)
            else:
                _content_slide(prs, st_title, bullets, notes)

    path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(path))
    return path
