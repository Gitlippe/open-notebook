"""Run every artifact demo end-to-end and print a consolidated summary."""
from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path

_WORKSPACE = Path(__file__).resolve().parent.parent
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))


DEMOS = [
    "demos.demo_briefing",
    "demos.demo_study_guide",
    "demos.demo_faq",
    "demos.demo_research_review",
    "demos.demo_flashcards",
    "demos.demo_quiz",
    "demos.demo_mindmap",
    "demos.demo_timeline",
    "demos.demo_infographic",
    "demos.demo_slide_deck",
    "demos.demo_pitch_deck",
    "demos.demo_paper_figure",
    "demos.demo_podcast_integration",
]


async def main() -> int:
    failures = []
    for modname in DEMOS:
        try:
            mod = importlib.import_module(modname)
            await mod.main()
        except Exception as exc:  # pragma: no cover - surfaced in demo output
            failures.append((modname, repr(exc)))
            print(f"!! {modname} failed: {exc!r}")

    print("\n" + "=" * 72)
    print(f"RAN {len(DEMOS)} demos  |  FAILURES: {len(failures)}")
    for name, err in failures:
        print(f"  - {name}: {err}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
