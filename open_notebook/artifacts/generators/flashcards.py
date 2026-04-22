"""Flashcard artifact generator (Anki .apkg + JSON).

Uses ``chunked_generate`` + provider-native structured output to produce a
fully-validated ``FlashcardsSchema`` instance. No heuristic fallback.
"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.llm import combine_prompts
from open_notebook.artifacts.prompts import build_flashcards_prompt
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers import anki_renderer


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------


class FlashcardSchema(BaseModel):
    """A single Anki-compatible flashcard."""

    front: str = Field(..., description="Question or cloze prompt")
    back: str = Field(..., description="Complete answer with explanation")
    tags: List[str] = Field(default_factory=list, description="1-3 lowercase hyphenated tags")


class FlashcardsSchema(BaseModel):
    """Validated output of a flashcard deck artifact."""

    title: str = Field(..., description="Flashcards: <topic>")
    cards: List[FlashcardSchema] = Field(
        ..., description="Flashcard deck, varied cognitive levels"
    )


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


@register_generator
class FlashcardsGenerator(BaseArtifactGenerator):
    """Anki-compatible flashcard deck with Q&A and tags."""

    artifact_type = "flashcards"
    description = "Anki-compatible flashcard deck (.apkg) with Q&A and tags."
    default_model_type = "transformation"

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        card_count: int = int(request.config.get("card_count", 12))
        instructions = build_flashcards_prompt(card_count=card_count)

        def map_prompt(chunk: str) -> str:
            return combine_prompts(instructions, chunk)

        def reduce_prompt(partials: list) -> str:
            all_cards = []
            for p in partials:
                for card in p.cards:
                    all_cards.append(
                        f"Front: {card.front}\nBack: {card.back}\nTags: {', '.join(card.tags)}"
                    )
            combined_text = "\n\n---\n\n".join(all_cards)
            synthesis_instructions = (
                build_flashcards_prompt(card_count=card_count)
                + "\n\nYou are consolidating flashcards from multiple source chunks. "
                "Remove duplicate or near-duplicate cards. Keep the best "
                f"{card_count} cards with the greatest variety of cognitive levels."
            )
            return combine_prompts(synthesis_instructions, combined_text)

        result: FlashcardsSchema = await self.chunked_generate(
            request,
            schema=FlashcardsSchema,
            map_prompt_builder=map_prompt,
            reduce_prompt_builder=reduce_prompt,
        )

        title = result.title or request.title or "Flashcards"
        data = result.model_dump()
        data["title"] = title

        json_path = self.output_path(request, "json")
        anki_renderer.render_json(data, json_path)

        apkg_path = self.output_path(request, "apkg")
        anki_renderer.render_apkg(data, apkg_path)

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=title,
            summary=f"{len(result.cards)} flashcards",
            structured=data,
            files=[
                ArtifactFile(
                    path=str(apkg_path),
                    mime_type="application/octet-stream",
                    description="Anki deck (.apkg)",
                ),
                ArtifactFile(
                    path=str(json_path),
                    mime_type="application/json",
                    description="Structured JSON",
                ),
            ],
            provenance=self.llm.provenance,
            metadata={"card_count": len(result.cards)},
        )
