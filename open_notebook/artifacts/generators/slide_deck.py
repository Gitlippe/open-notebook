"""Slide-deck generator with narrative-arc planning and per-slide refinement."""
from __future__ import annotations

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers.pptx_renderer import render_deck
from open_notebook.artifacts.schemas import SlideDeck
from open_notebook.artifacts.workflow import (
    claims_to_context,
    draft_and_refine,
    extract_claims,
)


def _render_markdown(data: dict) -> str:
    lines = [f"# {data.get('title', 'Deck')}"]
    sub = data.get("subtitle")
    if sub:
        lines.append(f"_{sub}_")
    plan = data.get("plan", {})
    if plan:
        lines.append("")
        lines.append(f"**Arc:** {plan.get('narrative_arc')} · "
                     f"**Budget:** {plan.get('slide_budget')} slides · "
                     f"**Goal:** {plan.get('goal')}")
    for idx, slide in enumerate(data.get("slides", []), start=1):
        lines.append("")
        lines.append(f"## Slide {idx} [{slide.get('slide_type')}]: {slide.get('title', '')}")
        for b in slide.get("bullets", []):
            lines.append(f"- {b}")
        notes = slide.get("notes")
        if notes:
            lines.append("")
            lines.append(f"> {notes}")
    return "\n".join(lines).strip() + "\n"


SLIDE_DECK_DRAFT_SYSTEM = """\
You are designing an informational slide deck. Before drafting slide
content, choose the narrative arc that best serves the material
(problem-solution, chronological, compare-contrast, pyramid, hero-journey,
or scqa) and a slide budget of 6-16.

Output must conform to the SlideDeck schema.

Rules:
- First slide is a title slide (slide_type='title').
- Second slide is an agenda when the deck is longer than 8 slides.
- Use section dividers (slide_type='section') to separate major parts.
- When the source contains a salient statistic, include at least one
  slide_type='stat' slide that foregrounds that number.
- Closing slide is slide_type='closing' with a crisp takeaway.
- Each slide has 2-5 bullets. Bullets are sentences, not fragments.
- Presenter notes are what the speaker says — conversational, 40+ chars.
- Bullet content must be grounded in the claim set.
"""


@register_generator
class SlideDeckGenerator(BaseArtifactGenerator):
    artifact_type = "slide_deck"
    description = "Narrative-arc planned slide deck (.pptx) with typed slide layouts."

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        length = request.config.get("length", "standard")
        claims = await extract_claims(
            self.llm,
            request.combined_content(max_chars=20000),
            focus=f"{length} informational slide deck",
        )
        context = claims_to_context(claims, max_claims=25)
        deck = await draft_and_refine(
            self.llm,
            schema=SlideDeck,
            draft_system=SLIDE_DECK_DRAFT_SYSTEM + f"\nTarget length: {length}.",
            context=context,
            quality_floor=8,
        )
        data = deck.model_dump()
        data.setdefault("title", request.title or data["title"])

        pptx_path = self.output_path(request, "pptx")
        render_deck(data, pptx_path)
        md_path = self.output_path(request, "md")
        md_path.write_text(_render_markdown(data), encoding="utf-8")
        json_path = self.output_path(request, "json")
        json_path.write_text(deck.model_dump_json(indent=2), encoding="utf-8")

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=data["title"],
            summary=data.get("subtitle"),
            structured=data,
            files=[
                ArtifactFile(
                    path=str(pptx_path),
                    mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    description="Slide deck (.pptx)",
                ),
                ArtifactFile(path=str(md_path), mime_type="text/markdown"),
                ArtifactFile(path=str(json_path), mime_type="application/json"),
            ],
            metadata={
                "slide_count": len(data.get("slides", [])),
                "narrative_arc": data.get("plan", {}).get("narrative_arc"),
                "slide_types": sorted({s["slide_type"] for s in data.get("slides", [])}),
            },
        )
