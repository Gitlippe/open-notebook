"""Research review generator: adversarial, BLUF-first, claim-vs-contribution."""
from __future__ import annotations

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers import markdown as md
from open_notebook.artifacts.schemas import ResearchReview
from open_notebook.artifacts.workflow import (
    claims_to_context,
    draft_and_refine,
    extract_claims,
)

RESEARCH_REVIEW_DRAFT_SYSTEM = """\
You are writing a skeptical, internal peer review of a research paper or
technical write-up. The review goes to a practitioner team that needs to
decide whether to adopt, pilot, watch, or skip the ideas in it.

Output must conform to the ResearchReview schema.

Rules:
- BLUF first: a candid single paragraph. Start with an adjective
  ('Interesting but...', 'Useful...', 'Impressive yet...'). Name at least
  one concrete strength and one concrete weakness.
- Distinguish sharply between the authors' claimed contribution and their
  actual contribution. Call out any gap between the two.
- Methodological limitations must be specific. No generic 'needs more
  evaluation' unless the source itself explicitly admits it.
- Potential applications are concrete uses for the practitioner team,
  not reworded abstract of the paper.
- Verdict is a single word from {adopt, pilot, watch, skip}. Be decisive.
- Confidence is {high, medium, low} based on evidence strength in the
  source material.
- Never invent authors, affiliations, or resources not in the source.
"""

RESEARCH_REVIEW_CRITIQUE_SYSTEM = """\
You are a hostile senior reviewer re-reading a draft research review.
Find exactly where the review is too kind, where it ducks criticism,
where it over-claims, and where it restates the paper instead of
critiquing it. Score harshly: 6/10 is the default, 8+/10 is earned only
by reviews that would hold up in a practitioner read-out. Output must
conform to the Critique schema.
"""


@register_generator
class ResearchReviewGenerator(BaseArtifactGenerator):
    artifact_type = "research_review"
    description = "Skeptical internal research review with verdict and confidence."

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        tone = request.config.get("tone", "brutally honest, skeptical")
        claims = await extract_claims(
            self.llm,
            request.combined_content(max_chars=22000),
            focus="skeptical peer review identifying both strengths and weaknesses",
        )
        context = claims_to_context(claims, max_claims=30)
        review = await draft_and_refine(
            self.llm,
            schema=ResearchReview,
            draft_system=RESEARCH_REVIEW_DRAFT_SYSTEM + f"\nReview tone: {tone}.",
            context=context,
            critique_system=RESEARCH_REVIEW_CRITIQUE_SYSTEM,
            quality_floor=8,
            max_passes=2,
        )
        data = review.model_dump()
        data.setdefault("title", request.title or data["title"])

        md_path = self.output_path(request, "md")
        md.write(md_path, md.render_research_review(data))
        json_path = self.output_path(request, "json")
        json_path.write_text(review.model_dump_json(indent=2), encoding="utf-8")

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=data["title"],
            summary=data.get("bluf"),
            structured=data,
            files=[
                ArtifactFile(path=str(md_path), mime_type="text/markdown"),
                ArtifactFile(path=str(json_path), mime_type="application/json"),
            ],
            metadata={
                "tone": tone,
                "verdict": data.get("verdict"),
                "confidence": data.get("confidence"),
                "limitation_count": len(data.get("methodological_limitations", [])),
            },
        )
