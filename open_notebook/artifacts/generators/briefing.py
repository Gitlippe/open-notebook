"""Briefing (BLUF summary) artifact generator.

Uses ``chunked_generate`` + provider-native structured output to produce a
fully-validated ``BriefingSchema`` instance. No heuristic fallback.
"""
from __future__ import annotations

import json
from typing import List

from pydantic import BaseModel, Field

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.llm import combine_prompts
from open_notebook.artifacts.prompts import build_briefing_prompt
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers import markdown as md
from open_notebook.artifacts.renderers.docx_renderer import render_briefing_docx


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------


class BriefingSchema(BaseModel):
    """Validated output of a BLUF executive briefing."""

    title: str = Field(..., description="Short, descriptive title")
    audience: str = Field(..., description="Ideal reader description")
    bluf: str = Field(..., description="Bottom Line Up Front — single most important insight")
    key_points: List[str] = Field(
        ..., description="3-5 sharp bullets summarising findings"
    )
    supporting_details: List[str] = Field(
        default_factory=list, description="Data points / evidence bullets"
    )
    action_items: List[str] = Field(..., description="2-4 crisp action items")
    keywords: List[str] = Field(default_factory=list, description="5-8 subject tags")


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


@register_generator
class BriefingGenerator(BaseArtifactGenerator):
    """Executive BLUF briefing with key points and action items."""

    artifact_type = "briefing"
    description = "BLUF-style executive briefing with key points and action items."
    default_model_type = "transformation"

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        audience = str(request.config.get("audience", "Executive"))
        instructions = build_briefing_prompt(audience=audience)

        def map_prompt(chunk: str) -> str:
            return combine_prompts(instructions, chunk)

        def reduce_prompt(partials: list) -> str:
            combined_text = "\n\n---\n\n".join(
                f"PARTIAL:\nBLUF: {p.bluf}\n"
                f"Key Points: {', '.join(p.key_points)}\n"
                f"Action Items: {', '.join(p.action_items)}"
                for p in partials
            )
            synthesis_instructions = (
                build_briefing_prompt(audience=audience)
                + "\n\nYou are synthesising multiple partial briefings into one "
                "final cohesive briefing. Eliminate redundancy; keep the sharpest points."
            )
            return combine_prompts(synthesis_instructions, combined_text)

        result: BriefingSchema = await self.chunked_generate(
            request,
            schema=BriefingSchema,
            map_prompt_builder=map_prompt,
            reduce_prompt_builder=reduce_prompt,
        )

        title = result.title or request.title or "Executive Briefing"
        data = result.model_dump()
        data["title"] = title

        md_path = self.output_path(request, "md")
        md.write(md_path, md.render_briefing(data))

        docx_path = self.output_path(request, "docx")
        render_briefing_docx(data, docx_path)

        json_path = self.output_path(request, "json")
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=title,
            summary=result.bluf,
            structured=data,
            files=[
                ArtifactFile(
                    path=str(md_path),
                    mime_type="text/markdown",
                    description="Briefing (Markdown)",
                ),
                ArtifactFile(
                    path=str(docx_path),
                    mime_type=(
                        "application/vnd.openxmlformats-officedocument"
                        ".wordprocessingml.document"
                    ),
                    description="Briefing (Word)",
                ),
                ArtifactFile(
                    path=str(json_path),
                    mime_type="application/json",
                    description="Structured JSON",
                ),
            ],
            provenance=self.llm.provenance,
            metadata={"audience": audience, "source_count": len(request.sources)},
        )
