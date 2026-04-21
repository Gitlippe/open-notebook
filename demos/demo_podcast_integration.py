"""Demo: Combined workflow — generate multiple artifacts for a single source.

This is the pattern Open Notebook will use once the podcast generator
and the new artifact generators coexist: a single research source spawns
a briefing, a slide deck, a pitch deck, a timeline, and (when an AI
provider is wired up) a podcast episode via the existing
``generate_podcast`` command.

Running this demo offline exercises the artifact side. The podcast
integration is left as an optional branch that fires only when
``ARTIFACT_USE_LLM=1`` and a podcast-creator provider is configured.
"""
from __future__ import annotations

import asyncio

from demos._common import demo_output_dir, offline_mode, print_result
from open_notebook.artifacts import generate_artifact


SOURCE = {
    "title": "Open Notebook 1.9 Release Notes",
    "content": """
Open Notebook 1.9 ships a complete artifact generation suite: briefings,
study guides, FAQs, research reviews, flashcards, quizzes, mind maps,
timelines, infographics, slide decks, pitch decks, and publication
figures all live alongside the existing podcast generator.

Every artifact type has a structured Pydantic schema, a renderer that
produces an appropriate file format, a deterministic heuristic fallback
that works without any AI provider, and a LangGraph-compatible LLM
adapter that reuses the multi-provider Esperanto layer.

The job queue has been extended with a ``generate_artifact`` command
mirroring the existing ``generate_podcast`` command, so long-running
generations happen asynchronously with full progress tracking through
the ``/commands/{id}`` endpoint.

The new REST surface exposes three endpoints: ``GET /api/artifacts/types``,
``POST /api/artifacts/generate``, and ``GET /api/artifacts/download``.
Generated files are persisted under ``$DATA_FOLDER/artifacts`` and can
be downloaded directly or served through the frontend.
"""
}


async def main():
    print("DEMO: podcast_integration — multi-artifact workflow")
    print("=" * 72)

    results = []
    for kind, title in (
        ("briefing", "Open Notebook 1.9 Briefing"),
        ("slide_deck", "Open Notebook 1.9 Deck"),
        ("timeline", "Open Notebook Release Timeline"),
        ("infographic", "Open Notebook 1.9 Highlights"),
    ):
        result = await generate_artifact(
            kind,
            [SOURCE],
            title=title,
            output_dir=demo_output_dir("podcast_integration"),
        )
        results.append(result)
        print_result(result)

    print("\nArtifact files produced:")
    for r in results:
        for f in r.files:
            print(f"  [{r.artifact_type:12}] {f.path}")

    if offline_mode():
        print("\n(Set ARTIFACT_USE_LLM=1 and configure a podcast-creator "
              "provider to also trigger podcast generation.)")
    else:
        print("\n(Podcast generation is available via "
              "commands.podcast_commands.generate_podcast_command when the "
              "podcast-creator backend is configured.)")


if __name__ == "__main__":
    asyncio.run(main())
