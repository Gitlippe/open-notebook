"""Mind map generator: taxonomic hierarchy extraction with rendered outputs."""
from __future__ import annotations

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers import mindmap_renderer as mm
from open_notebook.artifacts.schemas import MindMap
from open_notebook.artifacts.workflow import (
    claims_to_context,
    draft_and_refine,
    extract_claims,
)

MINDMAP_DRAFT_SYSTEM = """\
You are extracting a taxonomic mind map from the source material.
Output must conform to the MindMap schema (hierarchical MindMapNode).

Rules:
- The central_topic is a short, descriptive label for the whole subject.
- 4-8 branches; each branch is a primary thematic area of the material.
- Branch labels are short (1-4 words).
- Each branch has 2-6 children; children may nest further when the source
  supports it, but depth rarely exceeds 3 levels.
- Do not invent branches that the source does not support.
- Avoid overlap: each claim should live in exactly one branch.
"""


@register_generator
class MindMapGenerator(BaseArtifactGenerator):
    artifact_type = "mindmap"
    description = "Taxonomic mind map (Mermaid, DOT, Markdown outline, optional PNG)."

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        claims = await extract_claims(
            self.llm,
            request.combined_content(max_chars=14000),
            focus="taxonomic mind map",
        )
        context = claims_to_context(claims, max_claims=25)
        mindmap = await draft_and_refine(
            self.llm,
            schema=MindMap,
            draft_system=MINDMAP_DRAFT_SYSTEM,
            context=context,
            quality_floor=7,
        )
        data = mindmap.model_dump()
        data["central_topic"] = request.title or data.get("central_topic", "Topic")

        # Mindmap renderers take flat branches ([{label, children: [str, ...]}]).
        flat_branches = []
        for branch in data.get("branches", []):
            children = [_flatten(c) for c in branch.get("children", [])]
            flat_branches.append({"label": branch["label"], "children": children})
        flat_data = {"central_topic": data["central_topic"], "branches": flat_branches}

        mmd_path = self.output_path(request, "mmd")
        mmd_path.write_text(mm.render_mermaid(flat_data), encoding="utf-8")
        dot_path = self.output_path(request, "dot")
        dot_path.write_text(mm.render_dot(flat_data), encoding="utf-8")
        md_path = self.output_path(request, "md")
        md_path.write_text(mm.render_markdown_outline(flat_data), encoding="utf-8")
        json_path = self.output_path(request, "json")
        json_path.write_text(mindmap.model_dump_json(indent=2), encoding="utf-8")

        files = [
            ArtifactFile(path=str(mmd_path), mime_type="text/x-mermaid"),
            ArtifactFile(path=str(dot_path), mime_type="text/vnd.graphviz"),
            ArtifactFile(path=str(md_path), mime_type="text/markdown"),
            ArtifactFile(path=str(json_path), mime_type="application/json"),
        ]
        png_path = self.output_path(request, "png")
        rendered = mm.render_graph_png(flat_data, png_path)
        if rendered:
            files.insert(0, ArtifactFile(
                path=str(rendered), mime_type="image/png",
                description="Mind map (PNG)",
            ))

        branch_count = len(flat_data["branches"])
        child_count = sum(
            len(b.get("children", [])) for b in flat_data["branches"]
        )
        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=data["central_topic"],
            summary=f"{branch_count} branches, {child_count} child nodes",
            structured=data,
            files=files,
            metadata={"branch_count": branch_count, "child_count": child_count},
        )


def _flatten(node: dict) -> str:
    label = node.get("label", "")
    children = node.get("children", []) or []
    if children:
        descendants = ", ".join(c.get("label", "") for c in children[:3])
        return f"{label} ({descendants})"
    return label
