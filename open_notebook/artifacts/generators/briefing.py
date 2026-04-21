"""Briefing (BLUF summary) artifact generator."""
from __future__ import annotations

import json
from pathlib import Path

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.llm import combine_prompts
from open_notebook.artifacts.prompts import BRIEFING_PROMPT
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers import markdown as md
from open_notebook.artifacts.renderers.docx_renderer import render_briefing_docx


@register_generator
class BriefingGenerator(BaseArtifactGenerator):
    artifact_type = "briefing"
    description = "BLUF-style executive briefing with key points and action items."

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        audience = request.config.get("audience", "Executive")
        directive = BRIEFING_PROMPT
        if audience:
            directive += f"\nThe target audience is: {audience}."
        prompt = combine_prompts(directive, request.combined_content(max_chars=12000))
        data = await self.llm.generate_json(
            prompt, artifact_type=self.artifact_type
        )
        data.setdefault("title", request.title or "Executive Briefing")

        md_path: Path = self.output_path(request, "md")
        md.write(md_path, md.render_briefing(data))

        docx_path: Path = self.output_path(request, "docx")
        render_briefing_docx(data, docx_path)

        json_path: Path = self.output_path(request, "json")
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=data["title"],
            summary=data.get("bluf"),
            structured=data,
            files=[
                ArtifactFile(path=str(md_path), mime_type="text/markdown",
                             description="Briefing (Markdown)"),
                ArtifactFile(path=str(docx_path),
                             mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                             description="Briefing (Word)"),
                ArtifactFile(path=str(json_path), mime_type="application/json",
                             description="Structured JSON"),
            ],
            metadata={"audience": audience, "source_count": len(request.sources)},
        )
