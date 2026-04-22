"""Research review artifact generator (skeptical, BLUF-first).

Schema-first, SOTA implementation using structured output via
``chunked_generate``. The reviewer takes the tone of a skeptical
practitioner: short, direct, identifying both strengths and
methodological weaknesses.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.llm import combine_prompts
from open_notebook.artifacts.prompts import (
    RESEARCH_REVIEW_MAP_PROMPT,
    RESEARCH_REVIEW_REDUCE_PROMPT,
)
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers import markdown as md


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class WhyWeCareSchema(BaseModel):
    direct_techniques: List[str] = Field(
        default_factory=list,
        description="Concrete techniques or ideas we could adopt",
    )
    cost_effectiveness: List[str] = Field(
        default_factory=list,
        description="Cost, ROI, or resource considerations",
    )
    limitations: List[str] = Field(
        default_factory=list,
        description="Critical flaws or open questions",
    )


class ResourceSchema(BaseModel):
    label: str = Field(..., description="Short label (e.g. 'arXiv', 'GitHub')")
    url: str = Field(..., description="Full URL")


class ResearchReviewSchema(BaseModel):
    title: str = Field(..., description="'Research Review: <paper/topic title>'")
    bluf: str = Field(
        ...,
        description="Bottom Line Up Front. Begin with a clear verdict (one sentence).",
    )
    notable_authors: List[str] = Field(
        default_factory=list,
        description="Key authors of the reviewed work",
    )
    affiliations: List[str] = Field(
        default_factory=list,
        description="Institutional affiliations",
    )
    short_take: str = Field(
        ...,
        description="3-6 sentence plain-language summary of the work",
    )
    why_we_care: WhyWeCareSchema = Field(
        default_factory=WhyWeCareSchema,
        description="Structured breakdown of relevance, techniques, and cost",
    )
    limitations: List[str] = Field(
        ...,
        description="Explicit methodological limitations or weaknesses",
    )
    potential_applications: List[str] = Field(
        ...,
        description="2-5 concrete use cases or internal applications",
    )
    resources: List[ResourceSchema] = Field(
        default_factory=list,
        description="Links to paper, code, datasets, etc.",
    )


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

@register_generator
class ResearchReviewGenerator(BaseArtifactGenerator):
    artifact_type = "research_review"
    description = (
        "Skeptical, BLUF-first peer review of a research paper or "
        "technical document. Includes limitations and applications."
    )
    default_model_type = "transformation"

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        tone = request.config.get("tone", "skeptical, candid")
        audience = request.config.get("audience", "technical practitioners")

        def map_prompt(chunk: str) -> str:
            directive = RESEARCH_REVIEW_MAP_PROMPT + (
                f"\nTone: {tone}. Audience: {audience}."
            )
            return combine_prompts(directive, chunk)

        def reduce_prompt(partials: list[ResearchReviewSchema]) -> str:
            combined_json = json.dumps(
                [p.model_dump() for p in partials], indent=2
            )
            return combine_prompts(
                RESEARCH_REVIEW_REDUCE_PROMPT + f"\nTone: {tone}. Audience: {audience}.",
                combined_json,
            )

        result: ResearchReviewSchema = await self.chunked_generate(
            request,
            schema=ResearchReviewSchema,
            map_prompt_builder=map_prompt,
            reduce_prompt_builder=reduce_prompt,
        )

        data = result.model_dump()

        md_path = self.output_path(request, "md")
        md.write(md_path, md.render_research_review(data))

        json_path = self.output_path(request, "json")
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=result.title,
            summary=result.bluf,
            structured=data,
            files=[
                ArtifactFile(
                    path=str(md_path),
                    mime_type="text/markdown",
                    description="Research Review (Markdown)",
                ),
                ArtifactFile(path=str(json_path), mime_type="application/json"),
            ],
            provenance=self.llm.provenance,
            metadata={
                "tone": tone,
                "author_count": len(result.notable_authors),
                "limitation_count": len(result.limitations),
            },
        )
