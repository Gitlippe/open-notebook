"""Markdown rendering helpers for artifact generators.

All public functions accept either Pydantic schema instances or plain dicts.

Public API
----------
render_briefing(schema)         -> str
render_study_guide(schema)      -> str
render_faq(schema)              -> str
render_quiz(schema)             -> str
render_timeline(schema)         -> str
render_mindmap(schema)          -> str
render_research_review(schema)  -> str
write(path, content)            -> Path
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _to_dict(schema) -> Dict[str, Any]:
    """Coerce a Pydantic model or plain dict to a dict."""
    if isinstance(schema, dict):
        return schema
    return schema.model_dump()


def _hr() -> str:
    return "\n\n---\n"


def _callout(label: str, content: str) -> str:
    """GFM blockquote callout block.  > **LABEL:** content"""
    return f"> **{label}:** {content}"


def _gfm_table(columns: List[str], rows: List[List[Any]]) -> str:
    """Render a GitHub-Flavoured Markdown table."""
    def _cell(v: Any) -> str:
        return str(v).replace("|", "\\|").replace("\n", " ")

    header = "| " + " | ".join(_cell(c) for c in columns) + " |"
    sep = "| " + " | ".join(":---" for _ in columns) + " |"
    lines = [header, sep]
    for row in rows:
        padded = list(row) + [""] * max(0, len(columns) - len(row))
        padded = padded[:len(columns)]
        lines.append("| " + " | ".join(_cell(v) for v in padded) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Briefing
# ---------------------------------------------------------------------------

def render_briefing(schema) -> str:
    data = _to_dict(schema)
    lines: List[str] = []
    title = data.get("title") or "Briefing"
    lines.append(f"# {title}")

    audience = data.get("audience")
    if audience:
        lines.append(f"\n_Audience: {audience}_")

    bluf = data.get("bluf")
    if bluf:
        lines.append("")
        lines.append(_callout("BLUF", str(bluf)))

    if kp := data.get("key_points") or []:
        lines.append(_hr())
        lines.append("## Key Points\n")
        for item in kp:
            lines.append(f"- {item}")

    if sd := data.get("supporting_details") or []:
        lines.append("")
        lines.append("## Supporting Details\n")
        for item in sd:
            lines.append(f"- {item}")

    if ai := data.get("action_items") or []:
        lines.append(_hr())
        lines.append("## Action Items\n")
        for i, item in enumerate(ai, 1):
            lines.append(f"{i}. {item}")

    if kw := data.get("keywords") or []:
        lines.append("\n---")
        lines.append(f"\n_Keywords: {', '.join(str(k) for k in kw)}_")

    return "\n".join(lines).strip() + "\n"


# ---------------------------------------------------------------------------
# Study Guide
# ---------------------------------------------------------------------------

def render_study_guide(schema) -> str:
    data = _to_dict(schema)
    lines: List[str] = []
    lines.append(f"# {data.get('title', 'Study Guide')}")

    if overview := data.get("overview"):
        lines.append("\n## Overview\n")
        lines.append(str(overview))

    if lo := data.get("learning_objectives") or []:
        lines.append(_hr())
        lines.append("## Learning Objectives\n")
        for i, obj in enumerate(lo, 1):
            lines.append(f"{i}. {obj}")

    if kc := data.get("key_concepts") or []:
        lines.append(_hr())
        lines.append("## Key Concepts\n")
        for concept in kc:
            lines.append(f"- {concept}")

    if glossary := data.get("glossary") or []:
        lines.append(_hr())
        lines.append("## Glossary\n")
        columns = ["Term", "Definition"]
        rows = []
        for item in glossary:
            if isinstance(item, dict):
                rows.append([item.get("term", ""), item.get("definition", "")])
            else:
                rows.append([str(item), ""])
        lines.append(_gfm_table(columns, rows))

    if dq := data.get("discussion_questions") or []:
        lines.append(_hr())
        lines.append("## Discussion Questions\n")
        for i, q in enumerate(dq, 1):
            lines.append(f"{i}. {q}")

    if fr := data.get("further_reading") or []:
        lines.append(_hr())
        lines.append("## Further Reading\n")
        for item in fr:
            text = str(item)
            if text.startswith(("http://", "https://")):
                lines.append(f"- [{text}]({text})")
            else:
                lines.append(f"- {text}")

    return "\n".join(lines).strip() + "\n"


# ---------------------------------------------------------------------------
# FAQ
# ---------------------------------------------------------------------------

def render_faq(schema) -> str:
    data = _to_dict(schema)
    lines: List[str] = [f"# {data.get('title', 'FAQ')}", ""]
    for i, item in enumerate(data.get("items", []), 1):
        if isinstance(item, dict):
            q = item.get("question", "")
            a = item.get("answer", "")
        else:
            q = str(item)
            a = ""
        lines.append(f"### Q{i}. {q}")
        lines.append("")
        lines.append(str(a))
        lines.append("")
    return "\n".join(lines).strip() + "\n"


# ---------------------------------------------------------------------------
# Quiz
# ---------------------------------------------------------------------------

def render_quiz(schema) -> str:
    data = _to_dict(schema)
    lines: List[str] = [f"# {data.get('title', 'Quiz')}", ""]
    for idx, q in enumerate(data.get("questions", []), start=1):
        if isinstance(q, dict):
            question = q.get("question", "")
            options = q.get("options", [])
            answer_idx = q.get("answer_index", -1)
            explanation = q.get("explanation", "")
        else:
            # Pydantic model
            question = q.question
            options = q.options
            answer_idx = q.answer_index
            explanation = q.explanation

        lines.append(f"### Q{idx}. {question}")
        lines.append("")
        for opt_idx, opt in enumerate(options):
            marker = " ✓" if opt_idx == answer_idx else ""
            lines.append(f"- [{chr(65 + opt_idx)}] {opt}{marker}")
        if explanation:
            lines.append("")
            lines.append(_callout("Explanation", str(explanation)))
        lines.append("")
    return "\n".join(lines).strip() + "\n"


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

def render_timeline(schema) -> str:
    data = _to_dict(schema)
    lines: List[str] = [f"# {data.get('title', 'Timeline')}", ""]

    events = data.get("events", [])
    if events:
        # GFM table: Date | Event | Significance
        columns = ["Date", "Event", "Significance"]
        rows = []
        for ev in events:
            if isinstance(ev, dict):
                rows.append([
                    ev.get("date", ""),
                    ev.get("event", ""),
                    ev.get("significance", ""),
                ])
            else:
                rows.append([ev.date, ev.event, getattr(ev, "significance", "")])
        lines.append(_gfm_table(columns, rows))
        lines.append("")
        lines.append(_hr())
        lines.append("")

        # Also detailed bullet view
        lines.append("## Detailed Timeline\n")
        for ev in events:
            if isinstance(ev, dict):
                date = ev.get("date", "")
                event = ev.get("event", "")
                sig = ev.get("significance", "")
            else:
                date = ev.date
                event = ev.event
                sig = getattr(ev, "significance", "")
            lines.append(f"- **{date}** — {event}")
            if sig:
                lines.append(f"  > {sig}")

    return "\n".join(lines).strip() + "\n"


# ---------------------------------------------------------------------------
# Mindmap
# ---------------------------------------------------------------------------

def render_mindmap(schema) -> str:
    data = _to_dict(schema)
    central = data.get("central_topic", "Topic")
    lines: List[str] = [f"# {central}", ""]
    for branch in data.get("branches", []):
        if isinstance(branch, dict):
            label = branch.get("label", "Branch")
            children = branch.get("children", [])
        else:
            label = branch.label
            children = branch.children
        lines.append(f"## {label}")
        for child in children:
            lines.append(f"- {child}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


# ---------------------------------------------------------------------------
# Research Review
# ---------------------------------------------------------------------------

def render_research_review(schema) -> str:
    data = _to_dict(schema)
    lines: List[str] = []
    lines.append(f"# {data.get('title', 'Research Review')}")

    if bluf := data.get("bluf"):
        lines.append("")
        lines.append(_callout("BLUF", str(bluf)))

    if authors := data.get("notable_authors") or []:
        lines.append("")
        lines.append(f"**Authors:** {', '.join(str(a) for a in authors)}")
    if affiliations := data.get("affiliations") or []:
        lines.append(f"**Affiliations:** {', '.join(str(a) for a in affiliations)}")

    if short_take := data.get("short_take"):
        lines.append(_hr())
        lines.append("## Short Take\n")
        lines.append(str(short_take))

    why = data.get("why_we_care") or {}
    if why:
        lines.append(_hr())
        lines.append("## Why We Care\n")
        if isinstance(why, dict):
            for label, bullets in why.items():
                if not bullets:
                    continue
                pretty = label.replace("_", " ").title()
                lines.append(f"### {pretty}")
                for b in bullets:
                    lines.append(f"- {b}")
        else:
            # List form
            for b in why:
                lines.append(f"- {b}")

    if limitations := data.get("limitations") or []:
        lines.append(_hr())
        lines.append("## Limitations\n")
        for lim in limitations:
            lines.append(f"- {lim}")

    if applications := data.get("potential_applications") or []:
        lines.append(_hr())
        lines.append("## Potential Applications\n")
        for app in applications:
            lines.append(f"- {app}")

    if resources := data.get("resources") or []:
        lines.append(_hr())
        lines.append("## Resources\n")
        for r in resources:
            if isinstance(r, dict):
                label = r.get("label") or r.get("url", "")
                url = r.get("url", "")
                if url:
                    lines.append(f"- [{label}]({url})")
                else:
                    lines.append(f"- {label}")
            else:
                lines.append(f"- {r}")

    return "\n".join(lines).strip() + "\n"


# ---------------------------------------------------------------------------
# write helper
# ---------------------------------------------------------------------------

def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
