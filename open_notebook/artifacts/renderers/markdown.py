"""Markdown rendering helpers for artifact generators."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


def render_briefing(data: Dict[str, Any]) -> str:
    lines: List[str] = []
    title = data.get("title") or "Briefing"
    lines.append(f"# {title}")
    audience = data.get("audience")
    if audience:
        lines.append(f"_Audience: {audience}_")
    bluf = data.get("bluf")
    if bluf:
        lines.append("")
        lines.append(f"**BLUF:** {bluf}")
    kp = data.get("key_points") or []
    if kp:
        lines.append("")
        lines.append("## Key Points")
        for item in kp:
            lines.append(f"- {item}")
    sd = data.get("supporting_details") or []
    if sd:
        lines.append("")
        lines.append("## Supporting Details")
        for item in sd:
            lines.append(f"- {item}")
    ai = data.get("action_items") or []
    if ai:
        lines.append("")
        lines.append("## Action Items")
        for item in ai:
            lines.append(f"- {item}")
    return "\n".join(lines).strip() + "\n"


def render_study_guide(data: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# {data.get('title', 'Study Guide')}")
    if data.get("overview"):
        lines.append("")
        lines.append("## Overview")
        lines.append(data["overview"])
    if data.get("learning_objectives"):
        lines.append("")
        lines.append("## Learning Objectives")
        for obj in data["learning_objectives"]:
            lines.append(f"- {obj}")
    if data.get("key_concepts"):
        lines.append("")
        lines.append("## Key Concepts")
        for kc in data["key_concepts"]:
            lines.append(f"- {kc}")
    if data.get("glossary"):
        lines.append("")
        lines.append("## Glossary")
        for item in data["glossary"]:
            term = item.get("term", "")
            definition = item.get("definition", "")
            lines.append(f"- **{term}**: {definition}")
    if data.get("discussion_questions"):
        lines.append("")
        lines.append("## Discussion Questions")
        for q in data["discussion_questions"]:
            lines.append(f"- {q}")
    return "\n".join(lines).strip() + "\n"


def render_faq(data: Dict[str, Any]) -> str:
    lines = [f"# {data.get('title', 'FAQ')}", ""]
    for item in data.get("items", []):
        lines.append(f"### {item.get('question', '')}")
        lines.append(item.get("answer", ""))
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_research_review(data: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# {data.get('title', 'Research Review')}")
    if data.get("bluf"):
        lines.append("")
        lines.append(f"**BLUF:** {data['bluf']}")
    if data.get("notable_authors"):
        lines.append("")
        lines.append(f"**Authors:** {', '.join(data['notable_authors'])}")
    if data.get("affiliations"):
        lines.append(f"**Affiliations:** {', '.join(data['affiliations'])}")
    if data.get("short_take"):
        lines.append("")
        lines.append("## Short Take")
        lines.append(data["short_take"])
    why = data.get("why_we_care") or {}
    if why:
        lines.append("")
        lines.append("## Why We Care")
        for label, bullets in why.items():
            if not bullets:
                continue
            pretty = label.replace("_", " ").title()
            lines.append(f"### {pretty}")
            for b in bullets:
                lines.append(f"- {b}")
    if data.get("limitations"):
        lines.append("")
        lines.append("## Limitations")
        for l in data["limitations"]:
            lines.append(f"- {l}")
    if data.get("potential_applications"):
        lines.append("")
        lines.append("## Potential Applications")
        for a in data["potential_applications"]:
            lines.append(f"- {a}")
    if data.get("resources"):
        lines.append("")
        lines.append("## Resources")
        for r in data["resources"]:
            if isinstance(r, dict):
                lines.append(f"- {r.get('label', r.get('url', ''))}: {r.get('url', '')}")
            else:
                lines.append(f"- {r}")
    return "\n".join(lines).strip() + "\n"


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
