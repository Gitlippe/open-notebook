"""Study guide artifact generator."""
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
from open_notebook.artifacts.prompts import STUDY_GUIDE_PROMPT
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers import markdown as md
from open_notebook.artifacts.renderers.docx_renderer import render_study_guide_docx


@register_generator
class StudyGuideGenerator(BaseArtifactGenerator):
    artifact_type = "study_guide"
    description = "Structured study guide with objectives, concepts, glossary, and questions."

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        directive = STUDY_GUIDE_PROMPT
        depth = request.config.get("depth")
        if depth:
            directive += f"\nDepth setting: {depth}."
        prompt = combine_prompts(directive, request.combined_content(max_chars=16000))
        data = await self.llm.generate_json(
            prompt, artifact_type=self.artifact_type
        )
        data.setdefault("title", request.title or "Study Guide")

        md_path = self.output_path(request, "md")
        md.write(md_path, md.render_study_guide(data))
        docx_path = self.output_path(request, "docx")
        render_study_guide_docx(data, docx_path)
        json_path = self.output_path(request, "json")
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=data["title"],
            summary=data.get("overview"),
            structured=data,
            files=[
                ArtifactFile(path=str(md_path), mime_type="text/markdown",
                             description="Study Guide (Markdown)"),
                ArtifactFile(path=str(docx_path),
                             mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                             description="Study Guide (Word)"),
                ArtifactFile(path=str(json_path), mime_type="application/json"),
            ],
            metadata={"source_count": len(request.sources)},
        )
