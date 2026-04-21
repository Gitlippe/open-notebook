"""Mind map renderers: Mermaid markdown + Graphviz DOT + PNG."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict


def _safe_id(text: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_]", "_", text)
    if not clean:
        return "node"
    if clean[0].isdigit():
        clean = "n_" + clean
    return clean[:40]


def render_mermaid(data: Dict[str, Any]) -> str:
    """Return a Mermaid mindmap syntax string."""
    lines = ["mindmap"]
    central = (data.get("central_topic") or "Topic").replace("\n", " ")
    lines.append(f"  root(({central}))")
    for branch in data.get("branches", []):
        label = (branch.get("label") or "Branch").replace("\n", " ")
        lines.append(f"    {label}")
        for child in branch.get("children", []) or []:
            child = str(child).replace("\n", " ")[:100]
            lines.append(f"      {child}")
    return "\n".join(lines) + "\n"


def render_dot(data: Dict[str, Any]) -> str:
    central_label = data.get("central_topic", "Topic")
    lines = [
        'digraph mindmap {',
        '  rankdir=LR;',
        '  node [shape=box, style="rounded,filled", fillcolor="#dbeafe", fontname="Helvetica"];',
        f'  root [label="{central_label}", fillcolor="#2563eb", fontcolor="white", '
        'fontsize=18, shape=ellipse];',
    ]
    for i, branch in enumerate(data.get("branches", [])):
        b_id = f"b{i}_{_safe_id(branch.get('label', 'b'))}"
        b_label = branch.get("label", "Branch").replace('"', "'")
        lines.append(
            f'  {b_id} [label="{b_label}", fillcolor="#93c5fd"];'
        )
        lines.append(f'  root -> {b_id};')
        for j, child in enumerate(branch.get("children", []) or []):
            c_id = f"{b_id}_c{j}"
            c_label = str(child).replace('"', "'")[:80]
            lines.append(
                f'  {c_id} [label="{c_label}", fillcolor="#e0f2fe"];'
            )
            lines.append(f'  {b_id} -> {c_id};')
    lines.append("}")
    return "\n".join(lines)


def render_graph_png(data: Dict[str, Any], path: Path) -> Path | None:
    """Render the mind map as a PNG if the Graphviz binary is installed.

    Returns ``None`` when Graphviz is unavailable; callers should treat the
    PNG output as optional.
    """
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


def render_markdown_outline(data: Dict[str, Any]) -> str:
    lines = [f"# {data.get('central_topic', 'Topic')}", ""]
    for branch in data.get("branches", []):
        lines.append(f"## {branch.get('label', 'Branch')}")
        for child in branch.get("children", []) or []:
            lines.append(f"- {child}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"
