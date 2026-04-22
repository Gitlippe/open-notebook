"""Study guide artifact generator.

Uses ``chunked_generate`` + provider-native structured output to produce a
fully-validated ``StudyGuideSchema`` instance. No heuristic fallback.
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
from open_notebook.artifacts.prompts import build_study_guide_prompt
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers import markdown as md
from open_notebook.artifacts.renderers.docx_renderer import render_study_guide_docx


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------


class GlossaryTermSchema(BaseModel):
    """A glossary entry."""

    term: str = Field(..., description="The term being defined")
    definition: str = Field(..., description="Self-contained one-sentence definition")


class StudyGuideSchema(BaseModel):
    """Validated output of a study guide artifact."""

    title: str = Field(..., description="Study Guide: <topic>")
    overview: str = Field(..., description="2-4 sentence summary of the subject")
    learning_objectives: List[str] = Field(
        ..., description="4-6 objectives starting with action verbs"
    )
    key_concepts: List[str] = Field(
        ..., description="5-8 concise self-contained concept sentences"
    )
    glossary: List[GlossaryTermSchema] = Field(
        ..., description="5-8 glossary entries"
    )
    discussion_questions: List[str] = Field(
        ..., description="4-6 open-ended discussion questions"
    )
    further_reading: List[str] = Field(
        default_factory=list, description="Optional follow-up topics or resources"
    )


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


@register_generator
class StudyGuideGenerator(BaseArtifactGenerator):
    """Structured study guide with objectives, concepts, glossary, and questions."""

    artifact_type = "study_guide"
    description = "Structured study guide with objectives, concepts, glossary, and questions."
    default_model_type = "transformation"

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        depth: str = str(request.config.get("depth", "standard"))
        instructions = build_study_guide_prompt(depth=depth)

        def map_prompt(chunk: str) -> str:
            return combine_prompts(instructions, chunk)

        def reduce_prompt(partials: list) -> str:
            partial_texts = []
            for p in partials:
                glossary_items = "; ".join(
                    f"{g.term}: {g.definition}" for g in p.glossary
                )
                partial_texts.append(
                    f"Overview: {p.overview}\n"
                    f"Objectives: {', '.join(p.learning_objectives)}\n"
                    f"Key Concepts: {', '.join(p.key_concepts)}\n"
                    f"Glossary: {glossary_items}\n"
                    f"Discussion Qs: {', '.join(p.discussion_questions)}"
                )
            combined_text = "\n\n---\n\n".join(partial_texts)
            synthesis_instructions = (
                build_study_guide_prompt(depth=depth)
                + "\n\nYou are synthesising partial study guides from multiple source chunks "
                "into one comprehensive, non-redundant study guide. Merge overlapping content; "
                "keep the most useful objectives, concepts, and discussion questions."
            )
            return combine_prompts(synthesis_instructions, combined_text)

        result: StudyGuideSchema = await self.chunked_generate(
            request,
            schema=StudyGuideSchema,
            map_prompt_builder=map_prompt,
            reduce_prompt_builder=reduce_prompt,
        )

        title = result.title or request.title or "Study Guide"
        data = result.model_dump()
        data["title"] = title

        md_path = self.output_path(request, "md")
        md.write(md_path, md.render_study_guide(data))

        docx_path = self.output_path(request, "docx")
        render_study_guide_docx(data, docx_path)

        json_path = self.output_path(request, "json")
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=title,
            summary=result.overview,
            structured=data,
            files=[
                ArtifactFile(
                    path=str(md_path),
                    mime_type="text/markdown",
                    description="Study Guide (Markdown)",
                ),
                ArtifactFile(
                    path=str(docx_path),
                    mime_type=(
                        "application/vnd.openxmlformats-officedocument"
                        ".wordprocessingml.document"
                    ),
                    description="Study Guide (Word)",
                ),
                ArtifactFile(
                    path=str(json_path),
                    mime_type="application/json",
                    description="Structured JSON",
                ),
            ],
            provenance=self.llm.provenance,
            metadata={
                "source_count": len(request.sources),
                "depth": depth,
            },
        )
