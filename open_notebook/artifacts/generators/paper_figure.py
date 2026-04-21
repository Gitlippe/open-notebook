"""Paper figure generator (publication-style chart + caption)."""
from __future__ import annotations

import json

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.llm import combine_prompts
from open_notebook.artifacts.prompts import PAPER_FIGURE_PROMPT
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers.chart_renderer import render_paper_figure


@register_generator
class PaperFigureGenerator(BaseArtifactGenerator):
    artifact_type = "paper_figure"
    description = "Publication-ready figure (PNG) with structured data and caption."

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        preferred = request.config.get("chart_type")
        directive = PAPER_FIGURE_PROMPT
        if preferred:
            directive += f"\nPreferred chart_type: {preferred}."
        prompt = combine_prompts(directive, request.combined_content(max_chars=14000))
        data = await self.llm.generate_json(
            prompt, artifact_type=self.artifact_type
        )
        data.setdefault("title", request.title or "Figure")

        png_path = self.output_path(request, "png")
        render_paper_figure(data, png_path)

        json_path = self.output_path(request, "json")
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=data["title"],
            summary=data.get("caption"),
            structured=data,
            files=[
                ArtifactFile(path=str(png_path), mime_type="image/png",
                             description="Figure (PNG)"),
                ArtifactFile(path=str(json_path), mime_type="application/json"),
            ],
            metadata={
                "chart_type": data.get("chart_type"),
                "series_count": len(data.get("series", [])),
            },
        )
