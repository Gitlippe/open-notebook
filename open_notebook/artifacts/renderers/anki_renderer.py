"""Flashcard renderer using genanki (.apkg) + JSON."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

import genanki


def _stable_id(text: str) -> int:
    h = hashlib.sha1(text.encode("utf-8")).hexdigest()
    return int(h[:15], 16) % (10**9)


def render_apkg(data: Dict[str, Any], path: Path) -> Path:
    title = data.get("title", "Flashcards")
    cards = data.get("cards") or []

    model = genanki.Model(
        _stable_id(title + "::model"),
        "Open Notebook Basic",
        fields=[{"name": "Front"}, {"name": "Back"}, {"name": "Tags"}],
        templates=[
            {
                "name": "Card 1",
                "qfmt": "{{Front}}",
                "afmt": '{{FrontSide}}<hr id="answer">{{Back}}',
            }
        ],
        css=(
            ".card { font-family: -apple-system, sans-serif; font-size: 18px; "
            "text-align: left; padding: 16px; color: #111; background: #fff; }"
        ),
    )

    deck = genanki.Deck(_stable_id(title), title)
    for card in cards:
        front = str(card.get("front", "")).strip()
        back = str(card.get("back", "")).strip()
        tags = card.get("tags") or []
        if not front or not back:
            continue
        note = genanki.Note(
            model=model,
            fields=[front, back, ", ".join(tags)],
            tags=[str(t).replace(" ", "_") for t in tags],
        )
        deck.add_note(note)

    path.parent.mkdir(parents=True, exist_ok=True)
    package = genanki.Package(deck)
    package.write_to_file(str(path))
    return path


def render_json(data: Dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path
