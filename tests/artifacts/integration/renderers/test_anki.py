"""Integration tests for anki_renderer — no real LLM calls.

Tests verify:
  - render() produces a valid .apkg file.
  - .apkg is a valid SQLite database.
  - Card count matches schema.
  - Deck title correct.
  - Tags applied to notes.
  - Deterministic GUID: same front text → same note GUID.
  - render_apkg() legacy alias works.
  - render_json() writes JSON correctly.
  - Empty/invalid cards are skipped gracefully.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def flashcards_data() -> Dict[str, Any]:
    return {
        "title": "Flashcards: Python Basics",
        "description": "Core Python flashcard deck for beginners.",
        "cards": [
            {
                "front": "What is a list comprehension?",
                "back": "A concise way to create lists using [expr for x in iter if cond].",
                "tags": ["python", "data-structures"],
            },
            {
                "front": "What does len() return?",
                "back": "The number of items in an object.",
                "tags": ["python", "built-ins"],
            },
            {
                "front": "How do you open a file safely?",
                "back": "Use `with open(path) as f:` to ensure the file is closed.",
                "tags": ["python", "file-io"],
            },
            {
                "front": "What is a generator?",
                "back": "A function that yields values lazily using `yield`.",
                "tags": ["python", "iterators"],
            },
        ],
    }


@pytest.fixture
def minimal_data() -> Dict[str, Any]:
    return {
        "title": "Minimal Deck",
        "cards": [
            {"front": "Q1", "back": "A1", "tags": []},
            {"front": "Q2", "back": "A2", "tags": ["tag-a"]},
        ],
    }


# ---------------------------------------------------------------------------
# Basic production tests
# ---------------------------------------------------------------------------

def test_render_produces_apkg(tmp_path: Path, flashcards_data: dict) -> None:
    from open_notebook.artifacts.renderers.anki_renderer import render

    out = tmp_path / "cards.apkg"
    result = render(flashcards_data, out)
    assert result == out
    assert out.exists()
    assert out.stat().st_size > 0


def test_apkg_is_valid_sqlite(tmp_path: Path, flashcards_data: dict) -> None:
    """An .apkg file is a ZIP; the embedded collection.anki2 is SQLite."""
    import zipfile

    from open_notebook.artifacts.renderers.anki_renderer import render

    out = tmp_path / "cards.apkg"
    render(flashcards_data, out)

    # .apkg is a ZIP archive
    assert zipfile.is_zipfile(str(out)), ".apkg should be a ZIP file"

    # Extract and open the SQLite collection
    with zipfile.ZipFile(str(out)) as zf:
        names = zf.namelist()
        # Should contain collection.anki2 or collection.anki21
        db_names = [n for n in names if n.endswith((".anki2", ".anki21"))]
        assert db_names, f"No Anki DB found in .apkg. Files: {names}"
        db_bytes = zf.read(db_names[0])

    db_path = tmp_path / "col.anki2"
    db_path.write_bytes(db_bytes)
    conn = sqlite3.connect(str(db_path))
    tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    conn.close()
    # Anki 2 collections must have 'notes' and 'cards'
    assert "notes" in tables, f"'notes' table missing. Got: {tables}"
    assert "cards" in tables, f"'cards' table missing. Got: {tables}"


def test_card_count_matches_schema(tmp_path: Path, flashcards_data: dict) -> None:
    """Note count in the SQLite collection should equal card count in schema."""
    import zipfile

    from open_notebook.artifacts.renderers.anki_renderer import render

    out = tmp_path / "cards.apkg"
    render(flashcards_data, out)

    with zipfile.ZipFile(str(out)) as zf:
        names = zf.namelist()
        db_names = [n for n in names if n.endswith((".anki2", ".anki21"))]
        db_bytes = zf.read(db_names[0])

    db_path = tmp_path / "col.anki2"
    db_path.write_bytes(db_bytes)
    conn = sqlite3.connect(str(db_path))
    note_count = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
    conn.close()

    expected = len(flashcards_data["cards"])
    assert note_count == expected, (
        f"Expected {expected} notes, got {note_count}"
    )


def test_deck_metadata(tmp_path: Path, flashcards_data: dict) -> None:
    """Deck title should appear in the collection metadata."""
    import zipfile

    from open_notebook.artifacts.renderers.anki_renderer import render

    out = tmp_path / "cards.apkg"
    render(flashcards_data, out)

    with zipfile.ZipFile(str(out)) as zf:
        names = zf.namelist()
        db_names = [n for n in names if n.endswith((".anki2", ".anki21"))]
        db_bytes = zf.read(db_names[0])

    db_path = tmp_path / "col.anki2"
    db_path.write_bytes(db_bytes)
    conn = sqlite3.connect(str(db_path))
    # Deck info is in the 'col' table as JSON in the 'decks' column
    row = conn.execute("SELECT decks FROM col").fetchone()
    conn.close()

    if row:
        decks_json = json.loads(row[0])
        deck_names = [d.get("name", "") for d in decks_json.values()]
        assert any("Python Basics" in n or "Flashcards" in n for n in deck_names), (
            f"Expected deck title not found. Decks: {deck_names}"
        )


def test_tags_applied(tmp_path: Path, flashcards_data: dict) -> None:
    """Tags from cards should appear in note tags column."""
    import zipfile

    from open_notebook.artifacts.renderers.anki_renderer import render

    out = tmp_path / "cards.apkg"
    render(flashcards_data, out)

    with zipfile.ZipFile(str(out)) as zf:
        names = zf.namelist()
        db_names = [n for n in names if n.endswith((".anki2", ".anki21"))]
        db_bytes = zf.read(db_names[0])

    db_path = tmp_path / "col.anki2"
    db_path.write_bytes(db_bytes)
    conn = sqlite3.connect(str(db_path))
    tags_rows = conn.execute("SELECT tags FROM notes").fetchall()
    conn.close()

    all_tags = " ".join(r[0] for r in tags_rows if r[0])
    assert "python" in all_tags.lower(), f"Expected 'python' tag. Got: {all_tags!r}"


# ---------------------------------------------------------------------------
# Deterministic GUID
# ---------------------------------------------------------------------------

def test_deterministic_guid(tmp_path: Path, minimal_data: dict) -> None:
    """Same front text → same GUID across two render calls."""
    import zipfile

    from open_notebook.artifacts.renderers.anki_renderer import render

    out1 = tmp_path / "deck1.apkg"
    out2 = tmp_path / "deck2.apkg"
    render(minimal_data, out1)
    render(minimal_data, out2)

    def _get_guids(apkg: Path) -> List[str]:
        with zipfile.ZipFile(str(apkg)) as zf:
            names = zf.namelist()
            db_names = [n for n in names if n.endswith((".anki2", ".anki21"))]
            db_bytes = zf.read(db_names[0])
        db_path = apkg.parent / (apkg.stem + "_col.anki2")
        db_path.write_bytes(db_bytes)
        conn = sqlite3.connect(str(db_path))
        guids = [r[0] for r in conn.execute("SELECT guid FROM notes").fetchall()]
        conn.close()
        return sorted(guids)

    guids1 = _get_guids(out1)
    guids2 = _get_guids(out2)
    assert guids1 == guids2, (
        f"GUIDs not deterministic. Run1: {guids1} Run2: {guids2}"
    )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_skip_invalid_cards(tmp_path: Path) -> None:
    """Cards with empty front or back should be silently skipped."""
    from open_notebook.artifacts.renderers.anki_renderer import render

    data = {
        "title": "Partial Deck",
        "cards": [
            {"front": "", "back": "No front", "tags": []},  # skip
            {"front": "Valid Q", "back": "", "tags": []},   # skip
            {"front": "Good Q", "back": "Good A", "tags": ["t"]},  # keep
        ],
    }
    out = tmp_path / "partial.apkg"
    render(data, out)
    assert out.exists()

    import zipfile
    with zipfile.ZipFile(str(out)) as zf:
        names = zf.namelist()
        db_names = [n for n in names if n.endswith((".anki2", ".anki21"))]
        db_bytes = zf.read(db_names[0])

    db_path = tmp_path / "partial_col.anki2"
    db_path.write_bytes(db_bytes)
    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
    conn.close()
    assert count == 1, f"Expected 1 valid card, got {count}"


def test_render_apkg_alias(tmp_path: Path, flashcards_data: dict) -> None:
    """render_apkg() legacy dict alias must behave identically to render()."""
    from open_notebook.artifacts.renderers.anki_renderer import render_apkg

    out = tmp_path / "legacy.apkg"
    result = render_apkg(flashcards_data, out)
    assert result.exists()
    assert result.stat().st_size > 0


def test_render_json(tmp_path: Path, flashcards_data: dict) -> None:
    from open_notebook.artifacts.renderers.anki_renderer import render_json

    out = tmp_path / "cards.json"
    render_json(flashcards_data, out)
    loaded = json.loads(out.read_text())
    assert loaded["title"] == flashcards_data["title"]
    assert len(loaded["cards"]) == len(flashcards_data["cards"])


def test_render_creates_parent_dir(tmp_path: Path, minimal_data: dict) -> None:
    from open_notebook.artifacts.renderers.anki_renderer import render

    out = tmp_path / "nested" / "deeply" / "deck.apkg"
    render(minimal_data, out)
    assert out.exists()
