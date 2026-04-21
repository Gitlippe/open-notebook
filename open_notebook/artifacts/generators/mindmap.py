"""Mind map artifact generator (Mermaid + Graphviz + PNG)."""
from __future__ import annotations

import json

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.llm import combine_prompts
from open_notebook.artifacts.prompts import MINDMAP_PROMPT
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers import mindmap_renderer as mm


@register_generator
class MindMapGenerator(BaseArtifactGenerator):
    artifact_type = "mindmap"
    description = "Hierarchical mind map in Mermaid, Markdown outline, DOT, and PNG."

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        prompt = combine_prompts(MINDMAP_PROMPT, request.combined_content(max_chars=12000))
        data = await self.llm.generate_json(
            prompt, artifact_type=self.artifact_type
        )
        data.setdefault("central_topic", request.title or "Central Topic")

        mermaid_path = self.output_path(request, "mmd")
        mermaid_path.parent.mkdir(parents=True, exist_ok=True)
        mermaid_path.write_text(mm.render_mermaid(data), encoding="utf-8")

        dot_path = self.output_path(request, "dot")
        dot_path.write_text(mm.render_dot(data), encoding="utf-8")

        md_path = self.output_path(request, "md")
        md_path.write_text(mm.render_markdown_outline(data), encoding="utf-8")

        json_path = self.output_path(request, "json")
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        files = [
            ArtifactFile(path=str(mermaid_path), mime_type="text/x-mermaid",
                         description="Mermaid mindmap"),
            ArtifactFile(path=str(dot_path), mime_type="text/vnd.graphviz",
                         description="Graphviz DOT"),
            ArtifactFile(path=str(md_path), mime_type="text/markdown",
                         description="Markdown outline"),
            ArtifactFile(path=str(json_path), mime_type="application/json"),
        ]

        png_path = self.output_path(request, "png")
        rendered = mm.render_graph_png(data, png_path)
        if rendered:
            files.insert(
                0,
                ArtifactFile(path=str(rendered), mime_type="image/png",
                             description="Mind map (PNG)"),
            )

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=data.get("central_topic"),
            summary=(
                f"{len(data.get('branches', []))} branches, "
                f"{sum(len(b.get('children', []) or []) for b in data.get('branches', []))} sub-nodes"
            ),
            structured=data,
            files=files,
            metadata={"branch_count": len(data.get("branches", []))},
        )
