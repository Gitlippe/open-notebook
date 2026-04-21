"""Timeline artifact generator (structured JSON + PNG via matplotlib)."""
from __future__ import annotations

import json

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.llm import combine_prompts
from open_notebook.artifacts.prompts import TIMELINE_PROMPT
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers.chart_renderer import render_timeline


@register_generator
class TimelineGenerator(BaseArtifactGenerator):
    artifact_type = "timeline"
    description = "Chronological timeline rendered as a PNG with markdown summary."

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        prompt = combine_prompts(TIMELINE_PROMPT, request.combined_content(max_chars=16000))
        data = await self.llm.generate_json(
            prompt, artifact_type=self.artifact_type
        )
        data.setdefault("title", request.title or "Timeline")

        json_path = self.output_path(request, "json")
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        md_path = self.output_path(request, "md")
        md_lines = [f"# {data['title']}", ""]
        for ev in data.get("events", []):
            md_lines.append(f"- **{ev.get('date', '')}** — {ev.get('event', '')}")
        md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

        png_path = self.output_path(request, "png")
        render_timeline(data, png_path)

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=data["title"],
            summary=f"{len(data.get('events', []))} events",
            structured=data,
            files=[
                ArtifactFile(path=str(png_path), mime_type="image/png",
                             description="Timeline (PNG)"),
                ArtifactFile(path=str(md_path), mime_type="text/markdown"),
                ArtifactFile(path=str(json_path), mime_type="application/json"),
            ],
            metadata={"event_count": len(data.get("events", []))},
        )
