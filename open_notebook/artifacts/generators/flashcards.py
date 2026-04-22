"""Flashcards generator with Bloom diversity + Anki .apkg export."""
from __future__ import annotations

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers import anki_renderer
from open_notebook.artifacts.schemas import Flashcards
from open_notebook.artifacts.workflow import (
    claims_to_context,
    draft_and_refine,
    extract_claims,
)

FLASHCARDS_DRAFT_SYSTEM = """\
You are producing an Anki-style flashcard deck from the source material.
Output must conform to the Flashcards schema.

Rules:
- 10-15 cards. They must span at least three distinct Bloom levels.
- Mix card types: include at least one cloze deletion (use '{{c1::…}}'
  syntax) and at least one reversible card if the content allows.
- Fronts are succinct prompts; backs are complete answers.
- Tags are short, lowercase, and useful for filtering.
- Every card's content must be grounded in the claim set; no invented facts.
"""


@register_generator
class FlashcardsGenerator(BaseArtifactGenerator):
    artifact_type = "flashcards"
    description = "Anki flashcards spanning multiple Bloom cognitive levels."

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        count = request.config.get("card_count", 12)
        claims = await extract_claims(
            self.llm,
            request.combined_content(max_chars=14000),
            focus=f"generating ~{count} flashcards",
        )
        context = claims_to_context(claims, max_claims=20)
        deck = await draft_and_refine(
            self.llm,
            schema=Flashcards,
            draft_system=FLASHCARDS_DRAFT_SYSTEM + f"\nTarget {count} cards.",
            context=context,
            quality_floor=8,
        )
        data = deck.model_dump()
        data.setdefault("title", request.title or data["title"])
        # Anki renderer expects {'front', 'back', 'tags'} only — harmlessly ignores extras.

        apkg_path = self.output_path(request, "apkg")
        anki_renderer.render_apkg(data, apkg_path)
        json_path = self.output_path(request, "json")
        json_path.write_text(deck.model_dump_json(indent=2), encoding="utf-8")

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=data["title"],
            summary=f"{len(data['cards'])} flashcards spanning "
                    f"{len({c['bloom_level'] for c in data['cards']})} Bloom levels",
            structured=data,
            files=[
                ArtifactFile(path=str(apkg_path),
                             mime_type="application/octet-stream",
                             description="Anki deck (.apkg)"),
                ArtifactFile(path=str(json_path), mime_type="application/json"),
            ],
            metadata={
                "card_count": len(data["cards"]),
                "bloom_levels": sorted({c["bloom_level"] for c in data["cards"]}),
                "card_types": sorted({c["card_type"] for c in data["cards"]}),
            },
        )
