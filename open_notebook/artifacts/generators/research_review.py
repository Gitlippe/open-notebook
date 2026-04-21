"""Research review artifact generator (BLUF-style, skeptical internal review)."""
from __future__ import annotations

import json

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.llm import combine_prompts
from open_notebook.artifacts.prompts import RESEARCH_REVIEW_PROMPT
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers import markdown as md


@register_generator
class ResearchReviewGenerator(BaseArtifactGenerator):
    artifact_type = "research_review"
    description = (
        "Skeptical, BLUF-first peer review of a research paper or "
        "technical document. Includes limitations and applications."
    )

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        tone = request.config.get("tone", "skeptical, candid")
        directive = RESEARCH_REVIEW_PROMPT + f"\nTone: {tone}."
        prompt = combine_prompts(directive, request.combined_content(max_chars=20000))
        data = await self.llm.generate_json(
            prompt, artifact_type=self.artifact_type
        )
        data.setdefault("title", request.title or "Research Review")

        md_path = self.output_path(request, "md")
        md.write(md_path, md.render_research_review(data))
        json_path = self.output_path(request, "json")
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=data["title"],
            summary=data.get("bluf"),
            structured=data,
            files=[
                ArtifactFile(path=str(md_path), mime_type="text/markdown",
                             description="Research Review (Markdown)"),
                ArtifactFile(path=str(json_path), mime_type="application/json"),
            ],
            metadata={"tone": tone},
        )
