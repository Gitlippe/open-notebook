"""Flashcard renderer using genanki (.apkg).

Public API
----------
render(schema: FlashcardsSchema | dict, output_path: Path) -> Path
    Writes an Anki package (.apkg) and returns its path.

render_apkg(data: dict, path: Path) -> Path  — legacy dict alias
render_json(data: dict, path: Path) -> Path  — JSON dump helper
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def _stable_id(text: str) -> int:
    """Deterministic integer ID from a string (SHA-1 truncated to 9 decimal digits)."""
    h = hashlib.sha1(text.encode("utf-8")).hexdigest()
    return int(h[:15], 16) % (10**9)


def _to_dict(schema) -> Dict[str, Any]:
    if isinstance(schema, dict):
        return schema
    return schema.model_dump()


# ---------------------------------------------------------------------------
# Model / CSS
# ---------------------------------------------------------------------------

_CARD_CSS = """\
.card {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 18px;
  line-height: 1.5;
  text-align: left;
  padding: 20px;
  color: #111827;
  background: #ffffff;
}
.front-label {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #6b7280;
  margin-bottom: 8px;
}
hr.answer-divider {
  border: none;
  border-top: 1px solid #e5e7eb;
  margin: 16px 0;
}
.tags-line {
  font-size: 11px;
  color: #9ca3af;
  margin-top: 12px;
}
"""

_FRONT_TMPL = """\
<div class="front-label">Question</div>
<div class="front-text">{{Front}}</div>
"""

_BACK_TMPL = """\
{{FrontSide}}
<hr id="answer" class="answer-divider">
<div class="back-text">{{Back}}</div>
{{#Tags}}<div class="tags-line">Tags: {{Tags}}</div>{{/Tags}}
"""


def _build_model(title: str):
    """Build a genanki.Model for the deck."""
    import genanki

    return genanki.Model(
        _stable_id(title + "::model::v2"),
        "Open Notebook Basic v2",
        fields=[
            {"name": "Front"},
            {"name": "Back"},
            {"name": "Tags"},
        ],
        templates=[
            {
                "name": "Card 1",
                "qfmt": _FRONT_TMPL,
                "afmt": _BACK_TMPL,
            }
        ],
        css=_CARD_CSS,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render(schema, output_path: Path) -> Path:
    """Render a FlashcardsSchema (or dict) to an Anki .apkg file.

    Parameters
    ----------
    schema:
        FlashcardsSchema Pydantic model or a dict with ``title`` and
        ``cards`` (list of {front, back, tags}) keys.
    output_path:
        Destination file path.  Parent directories are created if needed.
        Should end with ``.apkg``.

    Returns
    -------
    Path
        The written .apkg path.
    """
    import genanki

    data = _to_dict(schema)
    title: str = str(data.get("title") or "Flashcards")
    cards: List[Dict[str, Any]] = data.get("cards") or []
    description: str = str(data.get("description") or f"Open Notebook flashcard deck: {title}")

    model = _build_model(title)

    deck_id = _stable_id(title + "::deck")
    deck = genanki.Deck(deck_id, title, description=description)

    skipped = 0
    for card in cards:
        if isinstance(card, dict):
            front = str(card.get("front", "")).strip()
            back = str(card.get("back", "")).strip()
            tags: List[str] = list(card.get("tags") or [])
        else:
            # Pydantic FlashcardSchema
            front = str(card.front).strip()
            back = str(card.back).strip()
            tags = list(card.tags or [])

        if not front or not back:
            skipped += 1
            continue

        # Normalise tags: lowercase, hyphenated, no spaces
        clean_tags = [str(t).lower().replace(" ", "-") for t in tags]
        tag_display = ", ".join(clean_tags)

        note = genanki.Note(
            model=model,
            fields=[front, back, tag_display],
            tags=clean_tags,
            guid=genanki.guid_for(front),  # deterministic from front text
        )
        deck.add_note(note)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    package = genanki.Package(deck)
    package.write_to_file(str(output_path))
    return output_path


# ---------------------------------------------------------------------------
# Backwards-compatible aliases
# ---------------------------------------------------------------------------

def render_apkg(data: Dict[str, Any], path: Path) -> Path:
    """Legacy dict-based alias — delegates to render()."""
    return render(data, path)


def render_json(data: Dict[str, Any], path: Path) -> Path:
    """Write a JSON dump of the flashcard data."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path
