"""FAQ artifact generator with grounded answers."""
from __future__ import annotations

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers import markdown as md
from open_notebook.artifacts.schemas import FAQ
from open_notebook.artifacts.workflow import (
    claims_to_context,
    draft_and_refine,
    extract_claims,
)

FAQ_DRAFT_SYSTEM = """\
You are producing a FAQ grounded in the source material. Output must
conform to the FAQ schema.

Rules:
- Generate 6-12 distinct Q&A pairs spanning different angles of the
  material (who/what/when/how/why/limitations).
- Questions are natural, specific, and something a reader would actually ask.
- Answers are complete, 2-4 sentences, and cite concrete facts from the
  source. Never evasive.
- Category is a short tag: 'pricing', 'migration', 'availability',
  'methodology', 'limitations', 'contact', etc. — choose what fits.
- Never repeat the same question in different words.
"""


@register_generator
class FAQGenerator(BaseArtifactGenerator):
    artifact_type = "faq"
    description = "Grounded FAQ with diverse, non-redundant Q&A pairs."

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        claims = await extract_claims(
            self.llm,
            request.combined_content(max_chars=16000),
            focus="FAQ generation",
        )
        context = claims_to_context(claims, max_claims=25)
        faq = await draft_and_refine(
            self.llm,
            schema=FAQ,
            draft_system=FAQ_DRAFT_SYSTEM,
            context=context,
            quality_floor=8,
        )
        data = faq.model_dump()
        data.setdefault("title", request.title or data["title"])

        md_path = self.output_path(request, "md")
        md.write(md_path, md.render_faq(data))
        json_path = self.output_path(request, "json")
        json_path.write_text(faq.model_dump_json(indent=2), encoding="utf-8")

        summary = data["items"][0]["answer"] if data.get("items") else None
        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=data["title"],
            summary=summary,
            structured=data,
            files=[
                ArtifactFile(path=str(md_path), mime_type="text/markdown"),
                ArtifactFile(path=str(json_path), mime_type="application/json"),
            ],
            metadata={"item_count": len(data.get("items", []))},
        )
