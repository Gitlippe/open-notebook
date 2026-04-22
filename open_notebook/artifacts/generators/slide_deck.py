"""Informational slide deck generator (.pptx).

Schema-first, SOTA implementation using structured output via
``chunked_generate``. Long inputs are fan-out / reduced automatically.
"""
from __future__ import annotations

import json
from typing import List, Optional

from pydantic import BaseModel, Field

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.llm import combine_prompts
from open_notebook.artifacts.prompts import SLIDE_DECK_MAP_PROMPT, SLIDE_DECK_REDUCE_PROMPT
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers.pptx_renderer import render_deck


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class SlideSchema(BaseModel):
    title: str = Field(..., description="Slide title")
    bullets: List[str] = Field(..., description="Bullet points for the slide body (2-5 items)")
    notes: Optional[str] = Field(None, description="Presenter speaker notes for this slide")


class SlideDeckSchema(BaseModel):
    title: str = Field(..., description="Deck title")
    subtitle: Optional[str] = Field(None, description="Short subtitle or tagline")
    slides: List[SlideSchema] = Field(
        ...,
        description="Ordered list of slides (7-10 slides, first=title, last=conclusion)",
    )


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _render_markdown(schema: SlideDeckSchema) -> str:
    lines = [f"# {schema.title}"]
    if schema.subtitle:
        lines.append(f"_{schema.subtitle}_")
    for idx, slide in enumerate(schema.slides, start=1):
        lines.append("")
        lines.append(f"## Slide {idx}: {slide.title}")
        for bullet in slide.bullets:
            lines.append(f"- {bullet}")
        if slide.notes:
            lines.append("")
            lines.append(f"> {slide.notes}")
    return "\n".join(lines).strip() + "\n"


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

@register_generator
class SlideDeckGenerator(BaseArtifactGenerator):
    artifact_type = "slide_deck"
    description = "Informational slide deck rendered as .pptx with speaker notes."
    default_model_type = "transformation"

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        target = request.config.get("length", "standard")
        audience = request.config.get("audience", "general")

        def map_prompt(chunk: str) -> str:
            directive = SLIDE_DECK_MAP_PROMPT + (
                f"\nTarget length: {target}. Audience: {audience}."
            )
            return combine_prompts(directive, chunk)

        def reduce_prompt(partials: list[SlideDeckSchema]) -> str:
            combined_json = json.dumps(
                [p.model_dump() for p in partials], indent=2
            )
            return combine_prompts(
                SLIDE_DECK_REDUCE_PROMPT + f"\nTarget length: {target}. Audience: {audience}.",
                combined_json,
            )

        result: SlideDeckSchema = await self.chunked_generate(
            request,
            schema=SlideDeckSchema,
            map_prompt_builder=map_prompt,
            reduce_prompt_builder=reduce_prompt,
        )

        # Fallback title from request if LLM left it generic
        if not result.title or result.title.lower() in {"presentation", "slide deck"}:
            if request.title:
                result = result.model_copy(update={"title": request.title})

        data = result.model_dump()

        pptx_path = self.output_path(request, "pptx")
        render_deck(data, pptx_path)

        md_path = self.output_path(request, "md")
        md_path.write_text(_render_markdown(result), encoding="utf-8")

        json_path = self.output_path(request, "json")
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=result.title,
            summary=result.subtitle or f"{len(result.slides)}-slide deck",
            structured=data,
            files=[
                ArtifactFile(
                    path=str(pptx_path),
                    mime_type=(
                        "application/vnd.openxmlformats-officedocument"
                        ".presentationml.presentation"
                    ),
                    description="Slide deck (.pptx)",
                ),
                ArtifactFile(path=str(md_path), mime_type="text/markdown",
                             description="Slide deck (Markdown preview)"),
                ArtifactFile(path=str(json_path), mime_type="application/json"),
            ],
            provenance=self.llm.provenance,
            metadata={
                "slide_count": len(result.slides),
                "target_length": target,
                "audience": audience,
            },
        )
