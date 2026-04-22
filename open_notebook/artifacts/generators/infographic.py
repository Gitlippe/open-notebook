"""Infographic artifact generator (PNG + HTML + JSON).

Schema-first, SOTA implementation using structured output via
``chunked_generate``. Produces a single-page visual summary with
stat blocks, section narratives, and a color theme.
"""
from __future__ import annotations

import json
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.llm import combine_prompts
from open_notebook.artifacts.prompts import (
    INFOGRAPHIC_MAP_PROMPT,
    INFOGRAPHIC_REDUCE_PROMPT,
)
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers.image_renderer import (
    render_infographic,
    render_infographic_html,
)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class InfographicSectionSchema(BaseModel):
    heading: str = Field(..., description="Short section heading (3-6 words)")
    text: str = Field(..., description="1-2 sentence narrative for this section")


class InfographicStatSchema(BaseModel):
    value: str = Field(
        ..., description="Standout metric or statistic (e.g. '82%', '3x', '$1.2B')"
    )
    label: str = Field(..., description="Short label describing the stat (4-8 words)")


class InfographicSchema(BaseModel):
    title: str = Field(..., description="Bold, short headline (5-8 words)")
    subtitle: Optional[str] = Field(None, description="One-sentence hook or context")
    sections: List[InfographicSectionSchema] = Field(
        ...,
        description="3-5 content sections, each with a heading and brief narrative",
    )
    stats: List[InfographicStatSchema] = Field(
        ...,
        description="3-4 standout data points to display prominently",
    )
    color_theme: Literal["blue", "green", "orange", "mono"] = Field(
        default="blue",
        description="Visual color theme for the infographic",
    )


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

@register_generator
class InfographicGenerator(BaseArtifactGenerator):
    artifact_type = "infographic"
    description = "Single-page PNG infographic with stat blocks and section layout."
    default_model_type = "transformation"

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        theme = request.config.get("color_theme", "blue")

        def map_prompt(chunk: str) -> str:
            directive = INFOGRAPHIC_MAP_PROMPT + f"\nPreferred color_theme: {theme}."
            return combine_prompts(directive, chunk)

        def reduce_prompt(partials: list[InfographicSchema]) -> str:
            combined_json = json.dumps(
                [p.model_dump() for p in partials], indent=2
            )
            return combine_prompts(
                INFOGRAPHIC_REDUCE_PROMPT + f"\nPreferred color_theme: {theme}.",
                combined_json,
            )

        result: InfographicSchema = await self.chunked_generate(
            request,
            schema=InfographicSchema,
            map_prompt_builder=map_prompt,
            reduce_prompt_builder=reduce_prompt,
        )

        data = result.model_dump()

        png_path = self.output_path(request, "png")
        render_infographic(data, png_path)

        html_path = self.output_path(request, "html")
        render_infographic_html(data, html_path)

        json_path = self.output_path(request, "json")
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=result.title,
            summary=result.subtitle or f"{len(result.sections)}-section infographic",
            structured=data,
            files=[
                ArtifactFile(
                    path=str(png_path),
                    mime_type="image/png",
                    description="Infographic (PNG)",
                ),
                ArtifactFile(
                    path=str(html_path),
                    mime_type="text/html",
                    description="Infographic (HTML)",
                ),
                ArtifactFile(path=str(json_path), mime_type="application/json"),
            ],
            provenance=self.llm.provenance,
            metadata={
                "section_count": len(result.sections),
                "stat_count": len(result.stats),
                "color_theme": result.color_theme,
            },
        )
