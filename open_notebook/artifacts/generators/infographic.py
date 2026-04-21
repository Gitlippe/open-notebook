"""Infographic artifact generator (PNG + HTML + JSON)."""
from __future__ import annotations

import json

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.llm import combine_prompts
from open_notebook.artifacts.prompts import INFOGRAPHIC_PROMPT
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers.image_renderer import (
    render_infographic,
    render_infographic_html,
)


@register_generator
class InfographicGenerator(BaseArtifactGenerator):
    artifact_type = "infographic"
    description = "Single-page PNG infographic with stat blocks and section layout."

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        theme = request.config.get("color_theme", "blue")
        directive = INFOGRAPHIC_PROMPT + f"\nPreferred color_theme: {theme}."
        prompt = combine_prompts(directive, request.combined_content(max_chars=12000))
        data = await self.llm.generate_json(
            prompt, artifact_type=self.artifact_type
        )
        data.setdefault("title", request.title or "Infographic")
        data.setdefault("color_theme", theme)

        png_path = self.output_path(request, "png")
        render_infographic(data, png_path)

        html_path = self.output_path(request, "html")
        render_infographic_html(data, html_path)

        json_path = self.output_path(request, "json")
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=data["title"],
            summary=data.get("subtitle"),
            structured=data,
            files=[
                ArtifactFile(path=str(png_path), mime_type="image/png",
                             description="Infographic (PNG)"),
                ArtifactFile(path=str(html_path), mime_type="text/html",
                             description="Infographic (HTML)"),
                ArtifactFile(path=str(json_path), mime_type="application/json"),
            ],
            metadata={
                "section_count": len(data.get("sections", [])),
                "stat_count": len(data.get("stats", [])),
                "color_theme": data.get("color_theme"),
            },
        )
