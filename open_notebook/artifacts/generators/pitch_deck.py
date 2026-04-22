"""Pitch deck generator following the canonical VC storytelling arc."""
from __future__ import annotations

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers.pptx_renderer import render_deck
from open_notebook.artifacts.schemas import PitchDeck
from open_notebook.artifacts.workflow import (
    claims_to_context,
    draft_and_refine,
    extract_claims,
)


def _render_markdown(data: dict) -> str:
    lines = [f"# {data.get('title', 'Pitch Deck')}"]
    if data.get("tagline"):
        lines.append(f"_{data['tagline']}_")
    for idx, slide in enumerate(data.get("slides", []), start=1):
        lines.append("")
        lines.append(f"## {idx}. [{slide.get('slide_type')}] {slide.get('title', '')}")
        for b in slide.get("bullets", []):
            lines.append(f"- {b}")
        notes = slide.get("notes")
        if notes:
            lines.append("")
            lines.append(f"> {notes}")
    return "\n".join(lines).strip() + "\n"


PITCH_DECK_DRAFT_SYSTEM = """\
You are building a venture-style pitch deck from the source material.
Output must conform to the PitchDeck schema.

Rules:
- Follow the canonical order: title → Problem → Solution → Market →
  Product → Business Model → Traction → Competition → Team → Ask.
- First slide is slide_type='title' with the company/product name and
  tagline. Final slide is slide_type='closing' with the ask.
- Include at least one slide_type='stat' for traction metrics when the
  source provides them.
- Bullets are concrete, audience-appropriate for a Series-stage investor.
  No jargon without explanation. No vague 'synergies'.
- Presenter notes describe what the founder says during delivery.
- Do not invent numbers; if the source is silent on a metric, say
  explicitly that it is TBD / available on request.
"""


@register_generator
class PitchDeckGenerator(BaseArtifactGenerator):
    artifact_type = "pitch_deck"
    description = "Investor pitch deck (.pptx) following canonical VC storytelling arc."

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        company = request.config.get("company", request.title or "Your Company")
        claims = await extract_claims(
            self.llm,
            request.combined_content(max_chars=20000),
            focus=f"pitch deck for {company}",
        )
        context = claims_to_context(claims, max_claims=25)
        deck = await draft_and_refine(
            self.llm,
            schema=PitchDeck,
            draft_system=PITCH_DECK_DRAFT_SYSTEM + f"\nCompany/Product: {company}.",
            context=context,
            quality_floor=8,
        )
        data = deck.model_dump()
        data.setdefault("title", company)
        data["subtitle"] = data.get("tagline")

        pptx_path = self.output_path(request, "pptx")
        render_deck(data, pptx_path)
        md_path = self.output_path(request, "md")
        md_path.write_text(_render_markdown(data), encoding="utf-8")
        json_path = self.output_path(request, "json")
        json_path.write_text(deck.model_dump_json(indent=2), encoding="utf-8")

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=data["title"],
            summary=data.get("tagline"),
            structured=data,
            files=[
                ArtifactFile(
                    path=str(pptx_path),
                    mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    description="Pitch deck (.pptx)",
                ),
                ArtifactFile(path=str(md_path), mime_type="text/markdown"),
                ArtifactFile(path=str(json_path), mime_type="application/json"),
            ],
            metadata={
                "slide_count": len(data.get("slides", [])),
                "company": company,
                "slide_types": sorted({s["slide_type"] for s in data.get("slides", [])}),
            },
        )
