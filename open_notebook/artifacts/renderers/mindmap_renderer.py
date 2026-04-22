"""Mind map renderers: Mermaid CLI → SVG/PNG, Graphviz DOT fallback.

Public API
----------
render(schema, output_path_stem) -> List[Path]
    Produces:
      - <stem>.mmd  — Mermaid source
      - <stem>.svg  — SVG (via mmdc or graphviz)
      - <stem>.png  — PNG (via mmdc or graphviz)

    If mermaid-cli (mmdc / npx @mermaid-js/mermaid-cli) is available it is
    used for high-fidelity SVG + PNG.  Otherwise graphviz is tried.  At
    minimum the .mmd source file is always produced.

Lower-level helpers kept for backwards compatibility:
  render_mermaid(data)         -> str
  render_dot(data)             -> str
  render_graph_png(data, path) -> Path | None
  render_markdown_outline(data)-> str
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Mermaid-CLI detection
# ---------------------------------------------------------------------------

def _find_mmdc() -> Optional[str]:
    """Return the mmdc command string if available, else None."""
    # Prefer global binary
    if shutil.which("mmdc"):
        return "mmdc"
    # Try npx
    npx = shutil.which("npx")
    if npx:
        return None  # We'll handle via npx separately
    return None


def _mmdc_via_npx() -> bool:
    """Return True if npx + @mermaid-js/mermaid-cli can be used."""
    npx = shutil.which("npx")
    if not npx:
        return False
    # Quick probe — check package exists without installing interactively
    try:
        result = subprocess.run(
            [npx, "--yes", "@mermaid-js/mermaid-cli", "--version"],
            capture_output=True,
            timeout=30,
            text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_id(text: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_]", "_", text)
    if not clean:
        return "node"
    if clean[0].isdigit():
        clean = "n_" + clean
    return clean[:40]


def _to_dict(schema) -> Dict[str, Any]:
    if isinstance(schema, dict):
        return schema
    return schema.model_dump()


# ---------------------------------------------------------------------------
# Mermaid source renderer
# ---------------------------------------------------------------------------

def render_mermaid(data: Dict[str, Any]) -> str:
    """Return a Mermaid mindmap syntax string."""
    lines = ["mindmap"]
    central = (data.get("central_topic") or "Topic").replace("\n", " ")
    # Escape special chars for Mermaid
    central_escaped = central.replace("(", "\\(").replace(")", "\\)")
    lines.append(f"  root(({central_escaped}))")
    for branch in data.get("branches", []):
        label = (branch.get("label") if isinstance(branch, dict) else branch.label) or "Branch"
        label = label.replace("\n", " ")[:80]
        lines.append(f"    {label}")
        children = branch.get("children", []) if isinstance(branch, dict) else branch.children
        for child in (children or []):
            child_str = str(child).replace("\n", " ")[:100]
            lines.append(f"      {child_str}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Graphviz DOT renderer
# ---------------------------------------------------------------------------

def render_dot(data: Dict[str, Any]) -> str:
    central_label = data.get("central_topic", "Topic")
    lines = [
        'digraph mindmap {',
        '  rankdir=LR;',
        '  node [shape=box, style="rounded,filled", fillcolor="#dbeafe", fontname="Helvetica"];',
        f'  root [label="{central_label}", fillcolor="#2563eb", fontcolor="white", '
        'fontsize=18, shape=ellipse];',
    ]
    branches = data.get("branches", [])
    for i, branch in enumerate(branches):
        if isinstance(branch, dict):
            b_label = branch.get("label", "Branch")
            b_children = branch.get("children", []) or []
        else:
            b_label = branch.label
            b_children = branch.children or []
        b_id = f"b{i}_{_safe_id(b_label)}"
        b_label_escaped = b_label.replace('"', "'")
        lines.append(f'  {b_id} [label="{b_label_escaped}", fillcolor="#93c5fd"];')
        lines.append(f'  root -> {b_id};')
        for j, child in enumerate(b_children):
            c_id = f"{b_id}_c{j}"
            c_label = str(child).replace('"', "'")[:80]
            lines.append(f'  {c_id} [label="{c_label}", fillcolor="#e0f2fe"];')
            lines.append(f'  {b_id} -> {c_id};')
    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Graphviz PNG renderer
# ---------------------------------------------------------------------------

def render_graph_png(data: Dict[str, Any], path: Path) -> Optional[Path]:
    """Render the mind map as a PNG using graphviz.  Returns None on failure."""
    try:
        import graphviz
    except Exception:
        return None
    dot_src = render_dot(data)
    try:
        src = graphviz.Source(dot_src)
        rendered = src.render(
            filename=path.stem,
            directory=str(path.parent),
            format="png",
            cleanup=True,
        )
    except Exception:
        return None
    rendered_path = Path(rendered)
    if rendered_path.exists() and rendered_path != path:
        rendered_path.rename(path)
    return path if path.exists() else None


def render_graph_svg(data: Dict[str, Any], path: Path) -> Optional[Path]:
    """Render the mind map as an SVG using graphviz.  Returns None on failure."""
    try:
        import graphviz
    except Exception:
        return None
    dot_src = render_dot(data)
    try:
        src = graphviz.Source(dot_src)
        rendered = src.render(
            filename=path.stem,
            directory=str(path.parent),
            format="svg",
            cleanup=True,
        )
    except Exception:
        return None
    rendered_path = Path(rendered)
    if rendered_path.exists() and rendered_path != path:
        rendered_path.rename(path)
    return path if path.exists() else None


# ---------------------------------------------------------------------------
# Mermaid CLI renderer
# ---------------------------------------------------------------------------

def _render_with_mmdc(
    mmd_path: Path,
    svg_path: Path,
    png_path: Path,
) -> List[Path]:
    """Use mmdc binary or npx to render Mermaid → SVG + PNG."""
    produced: List[Path] = []

    mmdc_cmd = shutil.which("mmdc")
    if mmdc_cmd:
        cmd_prefix = [mmdc_cmd]
    elif shutil.which("npx"):
        cmd_prefix = [shutil.which("npx"), "--yes", "@mermaid-js/mermaid-cli"]
    else:
        return produced

    # Render SVG
    try:
        result = subprocess.run(
            [*cmd_prefix, "-i", str(mmd_path), "-o", str(svg_path), "--quiet"],
            capture_output=True,
            timeout=60,
            text=True,
        )
        if result.returncode == 0 and svg_path.exists():
            produced.append(svg_path)
    except Exception:
        pass

    # Render PNG
    try:
        result = subprocess.run(
            [*cmd_prefix, "-i", str(mmd_path), "-o", str(png_path), "--quiet"],
            capture_output=True,
            timeout=60,
            text=True,
        )
        if result.returncode == 0 and png_path.exists():
            produced.append(png_path)
    except Exception:
        pass

    return produced


# ---------------------------------------------------------------------------
# Markdown outline
# ---------------------------------------------------------------------------

def render_markdown_outline(data: Dict[str, Any]) -> str:
    lines = [f"# {data.get('central_topic', 'Topic')}", ""]
    for branch in data.get("branches", []):
        if isinstance(branch, dict):
            label = branch.get("label", "Branch")
            children = branch.get("children", []) or []
        else:
            label = branch.label
            children = branch.children or []
        lines.append(f"## {label}")
        for child in children:
            lines.append(f"- {child}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


# ---------------------------------------------------------------------------
# Public high-level render() API
# ---------------------------------------------------------------------------

def render(schema, output_path_stem: Path) -> List[Path]:
    """Render a MindMapSchema to .mmd, .svg, .png files.

    Parameters
    ----------
    schema:
        A MindMapSchema Pydantic model or a compatible dict with
        ``central_topic`` and ``branches`` keys.
    output_path_stem:
        Path without extension, e.g. Path("/tmp/artifacts/mindmap").
        Files are written as <stem>.mmd, <stem>.svg, <stem>.png.

    Returns
    -------
    List[Path]
        All successfully produced file paths (always includes .mmd;
        .svg and .png depend on tool availability).
    """
    data = _to_dict(schema)
    stem = Path(output_path_stem)
    stem.parent.mkdir(parents=True, exist_ok=True)

    produced: List[Path] = []

    # 1. Always write the Mermaid source
    mmd_path = stem.with_suffix(".mmd")
    mmd_path.write_text(render_mermaid(data), encoding="utf-8")
    produced.append(mmd_path)

    svg_path = stem.with_suffix(".svg")
    png_path = stem.with_suffix(".png")

    # 2. Try mermaid-cli (mmdc or npx)
    has_mmdc = bool(shutil.which("mmdc"))
    has_npx = bool(shutil.which("npx"))

    if has_mmdc or has_npx:
        rendered = _render_with_mmdc(mmd_path, svg_path, png_path)
        produced.extend(rendered)

    # 3. Fallback to graphviz if mermaid-cli produced nothing
    if not any(p.suffix in (".svg", ".png") for p in produced):
        if render_graph_svg(data, svg_path):
            produced.append(svg_path)
        if render_graph_png(data, png_path):
            produced.append(png_path)

    return produced
