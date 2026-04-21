"""python-docx renderers for prose-style artifacts (study guides, briefings)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable

from docx import Document
from docx.shared import Pt


def _add_heading(doc: Document, text: str, level: int) -> None:
    if not text:
        return
    doc.add_heading(text, level=level)


def _add_bullets(doc: Document, items: Iterable[str]) -> None:
    for item in items:
        if item is None:
            continue
        doc.add_paragraph(str(item), style="List Bullet")


def render_briefing_docx(data: Dict[str, Any], path: Path) -> Path:
    doc = Document()
    styles = doc.styles["Normal"]
    styles.font.name = "Calibri"
    styles.font.size = Pt(11)

    doc.add_heading(data.get("title", "Briefing"), level=0)
    if data.get("audience"):
        p = doc.add_paragraph()
        p.add_run(f"Audience: {data['audience']}").italic = True
    if data.get("bluf"):
        p = doc.add_paragraph()
        r = p.add_run("BLUF: ")
        r.bold = True
        p.add_run(str(data["bluf"]))
    if data.get("key_points"):
        _add_heading(doc, "Key Points", 1)
        _add_bullets(doc, data["key_points"])
    if data.get("supporting_details"):
        _add_heading(doc, "Supporting Details", 1)
        _add_bullets(doc, data["supporting_details"])
    if data.get("action_items"):
        _add_heading(doc, "Action Items", 1)
        _add_bullets(doc, data["action_items"])
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    return path


def render_study_guide_docx(data: Dict[str, Any], path: Path) -> Path:
    doc = Document()
    doc.add_heading(data.get("title", "Study Guide"), level=0)
    if data.get("overview"):
        _add_heading(doc, "Overview", 1)
        doc.add_paragraph(str(data["overview"]))
    if data.get("learning_objectives"):
        _add_heading(doc, "Learning Objectives", 1)
        _add_bullets(doc, data["learning_objectives"])
    if data.get("key_concepts"):
        _add_heading(doc, "Key Concepts", 1)
        _add_bullets(doc, data["key_concepts"])
    if data.get("glossary"):
        _add_heading(doc, "Glossary", 1)
        for item in data["glossary"]:
            p = doc.add_paragraph(style="List Bullet")
            r = p.add_run(item.get("term", ""))
            r.bold = True
            p.add_run(f" — {item.get('definition', '')}")
    if data.get("discussion_questions"):
        _add_heading(doc, "Discussion Questions", 1)
        _add_bullets(doc, data["discussion_questions"])
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    return path
