"""Briefing (BLUF) generator.

Pipeline: claim extraction → structured draft → self-critique → refine.
Renders Markdown + DOCX + JSON.
"""
from __future__ import annotations

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers import markdown as md
from open_notebook.artifacts.renderers.docx_renderer import render_briefing_docx
from open_notebook.artifacts.schemas import Briefing
from open_notebook.artifacts.workflow import (
    claims_to_context,
    draft_and_refine,
    extract_claims,
)


BRIEFING_DRAFT_SYSTEM = """\
You are a senior analyst writing an executive briefing for a decision-making
audience. Your output must conform to the Briefing schema.

Rules:
- BLUF first: one sentence, no hedging, starts with the most decision-relevant
  finding. No "This briefing covers..."-style preamble.
- Key points are sharp declarative sentences. Each contains a concrete fact,
  number, or decision. No filler.
- Supporting details contain numbers, dates, names from the source only.
- Action items start with verbs and are executable by the named audience.
- Risks are real risks/dependencies identified in the source, not speculation.
- Do not invent facts. Only include what the extracted claim set supports.
"""


@register_generator
class BriefingGenerator(BaseArtifactGenerator):
    artifact_type = "briefing"
    description = "BLUF executive briefing with critique-refined claims."

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        audience = request.config.get("audience", "Executive leadership")
        claims = await extract_claims(
            self.llm,
            request.combined_content(max_chars=16000),
            focus=f"executive briefing for: {audience}",
        )
        context = (
            f"AUDIENCE: {audience}\n\n" + claims_to_context(claims, max_claims=20)
        )
        briefing = await draft_and_refine(
            self.llm,
            schema=Briefing,
            draft_system=BRIEFING_DRAFT_SYSTEM + f"\nAudience: {audience}.",
            context=context,
            quality_floor=8,
            max_passes=2,
        )

        data = briefing.model_dump()
        data.setdefault("title", request.title or data["title"])

        md_path = self.output_path(request, "md")
        md.write(md_path, md.render_briefing(data))
        docx_path = self.output_path(request, "docx")
        render_briefing_docx(data, docx_path)
        json_path = self.output_path(request, "json")
        json_path.write_text(briefing.model_dump_json(indent=2), encoding="utf-8")

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=data["title"],
            summary=data.get("bluf"),
            structured=data,
            files=[
                ArtifactFile(path=str(md_path), mime_type="text/markdown",
                             description="Briefing (Markdown)"),
                ArtifactFile(
                    path=str(docx_path),
                    mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    description="Briefing (Word)",
                ),
                ArtifactFile(path=str(json_path), mime_type="application/json"),
            ],
            metadata={
                "audience": audience,
                "claim_count": len(claims.claims),
                "pipeline": "claim_extraction → draft → critique → refine",
            },
        )
