"""Direct tests for renderers (independent of generator orchestration)."""
from __future__ import annotations

from pathlib import Path

import pytest

from open_notebook.artifacts.renderers import markdown as md
from open_notebook.artifacts.renderers.anki_renderer import render_apkg
from open_notebook.artifacts.renderers.chart_renderer import (
    render_paper_figure,
    render_timeline,
)
from open_notebook.artifacts.renderers.docx_renderer import (
    render_briefing_docx,
    render_study_guide_docx,
)
from open_notebook.artifacts.renderers.image_renderer import (
    render_infographic,
    render_infographic_html,
)
from open_notebook.artifacts.renderers.mindmap_renderer import (
    render_dot,
    render_markdown_outline,
    render_mermaid,
)
from open_notebook.artifacts.renderers.pptx_renderer import render_deck


def test_markdown_briefing_renders_sections():
    data = {
        "title": "T",
        "audience": "A",
        "bluf": "BLUF",
        "key_points": ["kp1"],
        "supporting_details": ["sd1"],
        "action_items": ["ai1"],
    }
    out = md.render_briefing(data)
    for needle in ["# T", "BLUF", "## Key Points", "- kp1", "## Action Items"]:
        assert needle in out


def test_markdown_faq_renders_items():
    data = {"title": "FAQ", "items": [{"question": "Q", "answer": "A"}]}
    out = md.render_faq(data)
    assert "### Q" in out and "A" in out


def test_docx_briefing_writes_file(tmp_path):
    out = render_briefing_docx(
        {"title": "T", "bluf": "b", "key_points": ["x"]},
        tmp_path / "b.docx",
    )
    assert out.exists()
    assert out.stat().st_size > 2000


def test_docx_study_guide_writes_file(tmp_path):
    out = render_study_guide_docx(
        {
            "title": "T",
            "overview": "ov",
            "learning_objectives": ["l1"],
            "key_concepts": ["k1"],
            "glossary": [{"term": "a", "definition": "b"}],
            "discussion_questions": ["dq"],
        },
        tmp_path / "sg.docx",
    )
    assert out.exists()


def test_mindmap_mermaid_shape():
    data = {
        "central_topic": "Core",
        "branches": [{"label": "B", "children": ["c1"]}],
    }
    mmd = render_mermaid(data)
    assert mmd.startswith("mindmap")
    assert "((Core))" in mmd


def test_mindmap_dot_shape():
    data = {
        "central_topic": "Core",
        "branches": [{"label": "B", "children": ["c1"]}],
    }
    dot = render_dot(data)
    assert "digraph mindmap" in dot
    assert "root ->" in dot


def test_mindmap_markdown_outline():
    data = {
        "central_topic": "Root",
        "branches": [{"label": "L", "children": ["x"]}],
    }
    out = render_markdown_outline(data)
    assert "# Root" in out and "## L" in out and "- x" in out


def test_pptx_deck_with_typed_slides(tmp_path):
    data = {
        "title": "Deck",
        "subtitle": "sub",
        "slides": [
            {"title": "Deck", "bullets": ["Opening"], "notes": "note", "slide_type": "title"},
            {"title": "Agenda", "bullets": ["One", "Two"], "notes": "note", "slide_type": "agenda"},
            {"title": "Details", "bullets": ["A", "B"], "notes": "note", "slide_type": "content"},
            {"title": "82% gain", "bullets": ["Big number"], "notes": "note", "slide_type": "stat"},
            {"title": "Thanks", "bullets": ["Q&A"], "notes": "note", "slide_type": "closing"},
        ],
    }
    out = render_deck(data, tmp_path / "d.pptx")
    assert out.exists()
    assert out.stat().st_size > 6000


def test_pptx_deck_empty_slides(tmp_path):
    out = render_deck({"title": "Only", "subtitle": "s"}, tmp_path / "e.pptx")
    assert out.exists()


def test_timeline_png_header(tmp_path):
    data = {
        "title": "T",
        "events": [
            {"date": "2020", "event": "e1"},
            {"date": "2024", "event": "e2"},
        ],
    }
    out = render_timeline(data, tmp_path / "t.png")
    assert out.read_bytes()[:8].startswith(b"\x89PNG")


def test_paper_figure_bar(tmp_path):
    data = {
        "title": "F",
        "chart_type": "bar",
        "x_label": "x",
        "y_label": "y",
        "series": [
            {"name": "s", "data": [{"x": "A", "y": 1}, {"x": "B", "y": 2}]}
        ],
    }
    out = render_paper_figure(data, tmp_path / "f.png")
    assert out.read_bytes()[:8].startswith(b"\x89PNG")


def test_paper_figure_line(tmp_path):
    data = {
        "title": "F",
        "chart_type": "line",
        "series": [
            {"name": "s", "data": [{"x": 1, "y": 1}, {"x": 2, "y": 2}]}
        ],
    }
    out = render_paper_figure(data, tmp_path / "f2.png")
    assert out.read_bytes()[:8].startswith(b"\x89PNG")


def test_infographic_png(tmp_path):
    data = {
        "title": "Infographic Title",
        "subtitle": "Subtitle goes here",
        "lede": "Lede sentence explaining the key point of the page.",
        "sections": [{"heading": "H", "text": "T" * 60, "icon_hint": "chart"}],
        "stats": [{"value": "1", "label": "x", "caveat": None}],
        "takeaway": "Here is the takeaway line.",
        "color_theme": "blue",
    }
    out = render_infographic(data, tmp_path / "i.png")
    assert out.read_bytes()[:8].startswith(b"\x89PNG")


def test_infographic_html_includes_takeaway(tmp_path):
    data = {
        "title": "I",
        "subtitle": "sub",
        "lede": "Lede line.",
        "sections": [{"heading": "H", "text": "T", "icon_hint": "spark"}],
        "stats": [{"value": "1", "label": "x"}],
        "takeaway": "Summary line.",
        "color_theme": "green",
    }
    out = render_infographic_html(data, tmp_path / "i.html")
    html = out.read_text()
    assert "<h1>" in html
    assert "takeaway" in html
    assert "Summary line." in html


def test_infographic_theme_fallback(tmp_path):
    data = {
        "title": "I",
        "subtitle": "sub",
        "lede": "Lede line.",
        "sections": [],
        "stats": [],
        "takeaway": "t",
        "color_theme": "not-a-theme",
    }
    out = render_infographic(data, tmp_path / "i.png")
    assert out.read_bytes()[:8].startswith(b"\x89PNG")


def test_anki_apkg(tmp_path):
    data = {
        "title": "Cards",
        "cards": [{"front": "F", "back": "B", "tags": ["t"]}],
    }
    out = render_apkg(data, tmp_path / "cards.apkg")
    assert out.exists()
    assert out.read_bytes()[:4] == b"PK\x03\x04"
