"""Study guide generator with Bloom-taxonomy learning objectives."""
from __future__ import annotations

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers import markdown as md
from open_notebook.artifacts.renderers.docx_renderer import render_study_guide_docx
from open_notebook.artifacts.schemas import StudyGuide
from open_notebook.artifacts.workflow import (
    claims_to_context,
    draft_and_refine,
    extract_claims,
)

STUDY_GUIDE_DRAFT_SYSTEM = """\
You are an instructional designer creating a structured study guide for
the material in the source context. Output must conform to the StudyGuide
schema.

Rules:
- Learning objectives must span multiple Bloom levels (at least three
  distinct levels across the set). Each statement begins with a verb that
  matches its bloom level (e.g., 'Explain' for understand, 'Apply' for
  apply, 'Critique' for evaluate).
- Glossary terms are pulled from the source; definitions are a complete
  sentence, not the term itself.
- Discussion questions are open-ended and require reasoning, not recall.
- Prerequisites, if any, are concrete prior knowledge the learner needs.
- Worked examples are step-by-step and only included when the source
  provides enough material for them.
"""


@register_generator
class StudyGuideGenerator(BaseArtifactGenerator):
    artifact_type = "study_guide"
    description = "Bloom-taxonomy aware study guide with critique-refined content."

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        depth = request.config.get("depth", "graduate")
        claims = await extract_claims(
            self.llm,
            request.combined_content(max_chars=18000),
            focus=f"study guide at {depth} depth",
        )
        context = (
            f"DEPTH: {depth}\n\n" + claims_to_context(claims, max_claims=25)
        )
        guide = await draft_and_refine(
            self.llm,
            schema=StudyGuide,
            draft_system=STUDY_GUIDE_DRAFT_SYSTEM + f"\nDepth level: {depth}.",
            context=context,
            quality_floor=8,
        )
        data = guide.model_dump()
        data.setdefault("title", request.title or data["title"])
        # Flatten bloom objectives to simple strings for the markdown renderer.
        data_for_render = dict(data)
        data_for_render["learning_objectives"] = [
            f"[{o['bloom_level']}] {o['statement']}" for o in data["learning_objectives"]
        ]

        md_path = self.output_path(request, "md")
        md.write(md_path, md.render_study_guide(data_for_render))
        docx_path = self.output_path(request, "docx")
        render_study_guide_docx(data_for_render, docx_path)
        json_path = self.output_path(request, "json")
        json_path.write_text(guide.model_dump_json(indent=2), encoding="utf-8")

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=data["title"],
            summary=data.get("overview"),
            structured=data,
            files=[
                ArtifactFile(path=str(md_path), mime_type="text/markdown"),
                ArtifactFile(
                    path=str(docx_path),
                    mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
                ArtifactFile(path=str(json_path), mime_type="application/json"),
            ],
            metadata={
                "depth": depth,
                "objective_count": len(data["learning_objectives"]),
                "bloom_levels": sorted({o["bloom_level"] for o in data["learning_objectives"]}),
            },
        )
