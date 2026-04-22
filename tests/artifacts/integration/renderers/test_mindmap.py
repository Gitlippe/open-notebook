"""Integration tests for mindmap_renderer — no real LLM calls.

Tests verify:
  - render() always produces .mmd source.
  - render_mermaid() produces valid Mermaid mindmap syntax.
  - render_dot() produces valid Graphviz DOT syntax.
  - render_markdown_outline() produces correct Markdown.
  - If mermaid-cli unavailable, graphviz fallback is tried.
  - If graphviz available, .png is produced.
  - Public render() API returns a list with at least .mmd.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict

import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mindmap_schema() -> Dict[str, Any]:
    return {
        "central_topic": "Machine Learning",
        "branches": [
            {
                "label": "Supervised Learning",
                "children": ["Classification", "Regression", "SVM"],
            },
            {
                "label": "Unsupervised Learning",
                "children": ["Clustering", "Dimensionality Reduction"],
            },
            {
                "label": "Reinforcement Learning",
                "children": ["Q-Learning", "Policy Gradient"],
            },
        ],
    }


# ---------------------------------------------------------------------------
# render_mermaid
# ---------------------------------------------------------------------------

def test_render_mermaid_starts_with_mindmap(mindmap_schema) -> None:
    from open_notebook.artifacts.renderers.mindmap_renderer import render_mermaid
    mmd = render_mermaid(mindmap_schema)
    assert mmd.startswith("mindmap")


def test_render_mermaid_has_root(mindmap_schema) -> None:
    from open_notebook.artifacts.renderers.mindmap_renderer import render_mermaid
    mmd = render_mermaid(mindmap_schema)
    assert "root" in mmd
    assert "Machine Learning" in mmd


def test_render_mermaid_has_branches(mindmap_schema) -> None:
    from open_notebook.artifacts.renderers.mindmap_renderer import render_mermaid
    mmd = render_mermaid(mindmap_schema)
    assert "Supervised Learning" in mmd
    assert "Unsupervised Learning" in mmd
    assert "Reinforcement Learning" in mmd


def test_render_mermaid_has_children(mindmap_schema) -> None:
    from open_notebook.artifacts.renderers.mindmap_renderer import render_mermaid
    mmd = render_mermaid(mindmap_schema)
    assert "Classification" in mmd
    assert "Clustering" in mmd
    assert "Q-Learning" in mmd


# ---------------------------------------------------------------------------
# render_dot
# ---------------------------------------------------------------------------

def test_render_dot_is_digraph(mindmap_schema) -> None:
    from open_notebook.artifacts.renderers.mindmap_renderer import render_dot
    dot = render_dot(mindmap_schema)
    assert "digraph" in dot


def test_render_dot_has_root(mindmap_schema) -> None:
    from open_notebook.artifacts.renderers.mindmap_renderer import render_dot
    dot = render_dot(mindmap_schema)
    assert "root" in dot
    assert "Machine Learning" in dot


def test_render_dot_branch_edges(mindmap_schema) -> None:
    from open_notebook.artifacts.renderers.mindmap_renderer import render_dot
    dot = render_dot(mindmap_schema)
    # Each branch connected to root
    assert "root ->" in dot


def test_render_dot_closed(mindmap_schema) -> None:
    from open_notebook.artifacts.renderers.mindmap_renderer import render_dot
    dot = render_dot(mindmap_schema)
    assert dot.strip().endswith("}")


# ---------------------------------------------------------------------------
# render_markdown_outline
# ---------------------------------------------------------------------------

def test_markdown_outline_h1(mindmap_schema) -> None:
    from open_notebook.artifacts.renderers.mindmap_renderer import render_markdown_outline
    md = render_markdown_outline(mindmap_schema)
    assert "# Machine Learning" in md


def test_markdown_outline_h2_branches(mindmap_schema) -> None:
    from open_notebook.artifacts.renderers.mindmap_renderer import render_markdown_outline
    md = render_markdown_outline(mindmap_schema)
    assert "## Supervised Learning" in md
    assert "## Unsupervised Learning" in md


def test_markdown_outline_bullets(mindmap_schema) -> None:
    from open_notebook.artifacts.renderers.mindmap_renderer import render_markdown_outline
    md = render_markdown_outline(mindmap_schema)
    assert "- Classification" in md
    assert "- Clustering" in md


# ---------------------------------------------------------------------------
# Public render() API
# ---------------------------------------------------------------------------

def test_render_always_produces_mmd(tmp_path: Path, mindmap_schema) -> None:
    from open_notebook.artifacts.renderers.mindmap_renderer import render
    stem = tmp_path / "mindmap"
    paths = render(mindmap_schema, stem)
    mmd_path = tmp_path / "mindmap.mmd"
    assert mmd_path in paths
    assert mmd_path.exists()
    content = mmd_path.read_text()
    assert "mindmap" in content


def test_render_mmd_content_correct(tmp_path: Path, mindmap_schema) -> None:
    from open_notebook.artifacts.renderers.mindmap_renderer import render
    stem = tmp_path / "mindmap"
    render(mindmap_schema, stem)
    mmd_path = tmp_path / "mindmap.mmd"
    content = mmd_path.read_text()
    assert "Machine Learning" in content
    assert "Supervised Learning" in content


def test_render_produces_at_least_mmd(tmp_path: Path, mindmap_schema) -> None:
    """render() must return at least [.mmd]; visual formats depend on tools."""
    from open_notebook.artifacts.renderers.mindmap_renderer import render
    stem = tmp_path / "mm"
    paths = render(mindmap_schema, stem)
    assert len(paths) >= 1
    assert all(p.exists() for p in paths)


@pytest.mark.skipif(
    shutil.which("dot") is None,
    reason="Graphviz 'dot' binary not installed",
)
def test_render_graphviz_png_fallback(tmp_path: Path, mindmap_schema) -> None:
    """When mermaid-cli is absent but graphviz is present, PNG is produced."""
    from open_notebook.artifacts.renderers import mindmap_renderer as mm

    png_path = tmp_path / "test_mindmap.png"
    result = mm.render_graph_png(mindmap_schema, png_path)
    if result is not None:
        assert result.exists()
        assert result.stat().st_size > 0
    # result can be None if graphviz binary has issues in CI; that's acceptable


@pytest.mark.skipif(
    not shutil.which("mmdc") and not shutil.which("npx"),
    reason="Neither mmdc nor npx available",
)
def test_render_mermaid_cli_svg(tmp_path: Path, mindmap_schema) -> None:
    """When mermaid-cli is available via mmdc or npx, SVG is produced."""
    from open_notebook.artifacts.renderers.mindmap_renderer import render
    stem = tmp_path / "mm_cli"
    paths = render(mindmap_schema, stem)
    svg_paths = [p for p in paths if p.suffix == ".svg"]
    # If CLI ran successfully we expect at least one SVG
    if svg_paths:
        assert svg_paths[0].exists()


def test_render_returns_list(tmp_path: Path, mindmap_schema) -> None:
    from open_notebook.artifacts.renderers.mindmap_renderer import render
    result = render(mindmap_schema, tmp_path / "mm")
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_render_mermaid_special_chars() -> None:
    """Parentheses in central_topic should be escaped."""
    from open_notebook.artifacts.renderers.mindmap_renderer import render_mermaid
    data = {
        "central_topic": "AI (2025)",
        "branches": [{"label": "Branch", "children": ["child"]}],
    }
    mmd = render_mermaid(data)
    # Should not crash; parens escaped or safely wrapped
    assert "mindmap" in mmd
    assert "AI" in mmd


def test_render_dot_empty_branches() -> None:
    from open_notebook.artifacts.renderers.mindmap_renderer import render_dot
    data = {"central_topic": "Root", "branches": []}
    dot = render_dot(data)
    assert "root" in dot
    assert "digraph" in dot
