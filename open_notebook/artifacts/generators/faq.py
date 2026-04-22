"""FAQ artifact generator.

Uses ``chunked_generate`` + provider-native structured output to produce a
fully-validated ``FAQSchema`` instance. No heuristic fallback.
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
from open_notebook.artifacts.prompts import build_faq_prompt
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers import markdown as md


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------


class FAQItemSchema(BaseModel):
    """A single Q&A pair."""

    question: str = Field(..., description="Realistic question a reader would ask")
    answer: str = Field(..., description="Complete, source-grounded answer")


class FAQSchema(BaseModel):
    """Validated output of a FAQ artifact."""

    title: str = Field(..., description="FAQ: <topic>")
    items: List[FAQItemSchema] = Field(..., description="6-10 diverse Q&A pairs")


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


@register_generator
class FAQGenerator(BaseArtifactGenerator):
    """Frequently asked questions and concise answers derived from sources."""

    artifact_type = "faq"
    description = "Frequently asked questions and concise answers derived from sources."
    default_model_type = "transformation"

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        max_items: int = int(request.config.get("max_items", 10))
        instructions = build_faq_prompt(max_items=max_items)

        def map_prompt(chunk: str) -> str:
            return combine_prompts(instructions, chunk)

        def reduce_prompt(partials: list) -> str:
            all_qa = []
            for p in partials:
                for item in p.items:
                    all_qa.append(f"Q: {item.question}\nA: {item.answer}")
            combined_text = "\n\n---\n\n".join(all_qa)
            synthesis_instructions = (
                build_faq_prompt(max_items=max_items)
                + "\n\nYou are consolidating Q&A pairs extracted from multiple "
                "source chunks. Remove duplicates and near-duplicates; keep the "
                f"best {max_items} most diverse, high-quality pairs."
            )
            return combine_prompts(synthesis_instructions, combined_text)

        result: FAQSchema = await self.chunked_generate(
            request,
            schema=FAQSchema,
            map_prompt_builder=map_prompt,
            reduce_prompt_builder=reduce_prompt,
        )

        title = result.title or request.title or "FAQ"
        data = result.model_dump()
        data["title"] = title

        md_path = self.output_path(request, "md")
        md.write(md_path, md.render_faq(data))

        json_path = self.output_path(request, "json")
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        summary = result.items[0].answer if result.items else None

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=title,
            summary=summary,
            structured=data,
            files=[
                ArtifactFile(
                    path=str(md_path),
                    mime_type="text/markdown",
                    description="FAQ (Markdown)",
                ),
                ArtifactFile(
                    path=str(json_path),
                    mime_type="application/json",
                    description="Structured JSON",
                ),
            ],
            provenance=self.llm.provenance,
            metadata={"item_count": len(result.items)},
        )
