"""Pitch deck generator (venture-style investor deck).

Schema-first, SOTA implementation using structured output via
``chunked_generate``. Uses the canonical VC slide structure:
Cover → Problem → Solution → Market → Product → Business Model →
Traction → Competition → Team → Financials → Ask.
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
from open_notebook.artifacts.prompts import PITCH_DECK_MAP_PROMPT, PITCH_DECK_REDUCE_PROMPT
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers.pptx_renderer import render_deck


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class PitchSlideSchema(BaseModel):
    title: str = Field(..., description="VC-canonical slide title (e.g. 'Problem', 'Ask')")
    bullets: List[str] = Field(
        ..., description="2-4 crisp, investor-facing bullet points"
    )
    notes: Optional[str] = Field(None, description="Presenter talking notes")


class PitchDeckSchema(BaseModel):
    title: str = Field(..., description="Company or product name")
    tagline: str = Field(..., description="One-line value proposition / positioning statement")
    slides: List[PitchSlideSchema] = Field(
        ...,
        description=(
            "8-12 slides in canonical VC order: Cover, Problem, Solution, Market, "
            "Product, Business Model, Traction, Competition, Team, Financials, Ask"
        ),
    )


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _render_markdown(schema: PitchDeckSchema) -> str:
    lines = [f"# {schema.title}", f"_{schema.tagline}_"]
    for idx, slide in enumerate(schema.slides, start=1):
        lines.append("")
        lines.append(f"## {idx}. {slide.title}")
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
class PitchDeckGenerator(BaseArtifactGenerator):
    artifact_type = "pitch_deck"
    description = "Investor-style pitch deck (.pptx) with canonical VC structure."
    default_model_type = "transformation"

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        company = request.config.get("company", request.title or "Your Company")
        stage = request.config.get("stage", "Series A")

        def map_prompt(chunk: str) -> str:
            directive = PITCH_DECK_MAP_PROMPT + (
                f"\nCompany/Product: {company}. Funding stage: {stage}."
            )
            return combine_prompts(directive, chunk)

        def reduce_prompt(partials: list[PitchDeckSchema]) -> str:
            combined_json = json.dumps(
                [p.model_dump() for p in partials], indent=2
            )
            return combine_prompts(
                PITCH_DECK_REDUCE_PROMPT + f"\nCompany/Product: {company}. Funding stage: {stage}.",
                combined_json,
            )

        result: PitchDeckSchema = await self.chunked_generate(
            request,
            schema=PitchDeckSchema,
            map_prompt_builder=map_prompt,
            reduce_prompt_builder=reduce_prompt,
        )

        data = result.model_dump()

        # pptx_renderer.render_deck expects subtitle_key="subtitle" or "tagline"
        pptx_data = dict(data)
        pptx_data["subtitle"] = result.tagline
        pptx_path = self.output_path(request, "pptx")
        render_deck(pptx_data, pptx_path)

        md_path = self.output_path(request, "md")
        md_path.write_text(_render_markdown(result), encoding="utf-8")

        json_path = self.output_path(request, "json")
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=result.title,
            summary=result.tagline,
            structured=data,
            files=[
                ArtifactFile(
                    path=str(pptx_path),
                    mime_type=(
                        "application/vnd.openxmlformats-officedocument"
                        ".presentationml.presentation"
                    ),
                    description="Pitch deck (.pptx)",
                ),
                ArtifactFile(path=str(md_path), mime_type="text/markdown",
                             description="Pitch deck (Markdown preview)"),
                ArtifactFile(path=str(json_path), mime_type="application/json"),
            ],
            provenance=self.llm.provenance,
            metadata={
                "slide_count": len(result.slides),
                "company": company,
                "stage": stage,
            },
        )
