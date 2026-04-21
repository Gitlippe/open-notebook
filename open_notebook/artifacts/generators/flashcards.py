"""Flashcard artifact generator (Anki + JSON)."""
from __future__ import annotations

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.llm import combine_prompts
from open_notebook.artifacts.prompts import FLASHCARDS_PROMPT
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers import anki_renderer


@register_generator
class FlashcardsGenerator(BaseArtifactGenerator):
    artifact_type = "flashcards"
    description = "Anki-compatible flashcard deck (.apkg) with Q&A and tags."

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        card_count = request.config.get("card_count", 12)
        directive = FLASHCARDS_PROMPT + f"\nTarget ~{card_count} cards."
        prompt = combine_prompts(directive, request.combined_content(max_chars=14000))
        data = await self.llm.generate_json(
            prompt, artifact_type=self.artifact_type
        )
        data.setdefault("title", request.title or "Flashcards")

        json_path = self.output_path(request, "json")
        anki_renderer.render_json(data, json_path)

        apkg_path = self.output_path(request, "apkg")
        anki_renderer.render_apkg(data, apkg_path)

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=data["title"],
            summary=f"{len(data.get('cards', []))} flashcards",
            structured=data,
            files=[
                ArtifactFile(path=str(apkg_path),
                             mime_type="application/octet-stream",
                             description="Anki deck (.apkg)"),
                ArtifactFile(path=str(json_path), mime_type="application/json"),
            ],
            metadata={"card_count": len(data.get("cards", []))},
        )
