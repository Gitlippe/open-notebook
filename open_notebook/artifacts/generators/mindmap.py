"""Mind map artifact generator (Mermaid + Graphviz DOT + PNG).

Uses ``chunked_generate`` + provider-native structured output to produce a
fully-validated ``MindMapSchema`` instance. No heuristic fallback.
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
from open_notebook.artifacts.prompts import build_mindmap_prompt
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers import mindmap_renderer as mm


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------


class MindMapBranchSchema(BaseModel):
    """A single primary branch of the mind map."""

    label: str = Field(..., description="Short label for this branch (<=6 words)")
    children: List[str] = Field(
        ..., description="2-5 distinct sub-concepts under this branch"
    )


class MindMapSchema(BaseModel):
    """Validated output of a mind map artifact."""

    central_topic: str = Field(..., description="Concise name for the central node")
    branches: List[MindMapBranchSchema] = Field(
        ..., description="5-7 mutually exclusive primary branches"
    )


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


@register_generator
class MindMapGenerator(BaseArtifactGenerator):
    """Hierarchical mind map in Mermaid, Markdown outline, DOT, and optional PNG."""

    artifact_type = "mindmap"
    description = "Hierarchical mind map in Mermaid, Markdown outline, DOT, and PNG."
    default_model_type = "transformation"

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        instructions = build_mindmap_prompt()

        def map_prompt(chunk: str) -> str:
            return combine_prompts(instructions, chunk)

        def reduce_prompt(partials: list) -> str:
            partial_texts = []
            for p in partials:
                branch_lines = [f"  - {b.label}: {', '.join(b.children)}" for b in p.branches]
                partial_texts.append(
                    f"Central: {p.central_topic}\n" + "\n".join(branch_lines)
                )
            combined_text = "\n\n---\n\n".join(partial_texts)
            synthesis_instructions = (
                build_mindmap_prompt()
                + "\n\nYou are synthesising partial mind maps from multiple source chunks "
                "into one unified, non-redundant mind map. Merge overlapping branches; "
                "keep 5-7 mutually exclusive top-level branches."
            )
            return combine_prompts(synthesis_instructions, combined_text)

        result: MindMapSchema = await self.chunked_generate(
            request,
            schema=MindMapSchema,
            map_prompt_builder=map_prompt,
            reduce_prompt_builder=reduce_prompt,
        )

        central_topic = result.central_topic or request.title or "Central Topic"
        data = result.model_dump()
        data["central_topic"] = central_topic

        # Use the high-level renderer which tries mermaid-cli first (best
        # quality) and falls back to graphviz. It always writes .mmd and
        # attempts .svg + .png. The generator also writes .dot, .md, .json
        # separately for reference.
        stem = self.output_path(request, "mmd").with_suffix("")
        stem.parent.mkdir(parents=True, exist_ok=True)
        rendered_paths = mm.render(data, stem)

        # Ensure .dot, .md, .json auxiliaries also exist (render() only writes
        # .mmd + attempted .svg/.png).
        dot_path = stem.with_suffix(".dot")
        dot_path.write_text(mm.render_dot(data), encoding="utf-8")

        md_path = stem.with_suffix(".md")
        md_path.write_text(mm.render_markdown_outline(data), encoding="utf-8")

        json_path = stem.with_suffix(".json")
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        # Build the ArtifactFile list: image first (PNG preferred, else SVG),
        # then source files.
        files: list[ArtifactFile] = []
        rendered_by_ext = {p.suffix: p for p in rendered_paths}
        if ".png" in rendered_by_ext:
            files.append(
                ArtifactFile(
                    path=str(rendered_by_ext[".png"]),
                    mime_type="image/png",
                    description="Mind map (PNG)",
                )
            )
        if ".svg" in rendered_by_ext:
            files.append(
                ArtifactFile(
                    path=str(rendered_by_ext[".svg"]),
                    mime_type="image/svg+xml",
                    description="Mind map (SVG)",
                )
            )
        if ".mmd" in rendered_by_ext:
            files.append(
                ArtifactFile(
                    path=str(rendered_by_ext[".mmd"]),
                    mime_type="text/x-mermaid",
                    description="Mermaid mindmap source",
                )
            )
        files.extend(
            [
                ArtifactFile(
                    path=str(dot_path),
                    mime_type="text/vnd.graphviz",
                    description="Graphviz DOT",
                ),
                ArtifactFile(
                    path=str(md_path),
                    mime_type="text/markdown",
                    description="Markdown outline",
                ),
                ArtifactFile(
                    path=str(json_path),
                    mime_type="application/json",
                    description="Structured JSON",
                ),
            ]
        )

        total_children = sum(len(b.children) for b in result.branches)
        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=central_topic,
            summary=(
                f"{len(result.branches)} branches, {total_children} sub-nodes"
            ),
            structured=data,
            files=files,
            provenance=self.llm.provenance,
            metadata={"branch_count": len(result.branches)},
        )
