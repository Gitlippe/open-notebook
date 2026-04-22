"""Infographic generator with data-driven layout and takeaway banner."""
from __future__ import annotations

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers.image_renderer import (
    render_infographic,
    render_infographic_html,
)
from open_notebook.artifacts.schemas import Infographic
from open_notebook.artifacts.workflow import (
    claims_to_context,
    draft_and_refine,
    extract_claims,
)

INFOGRAPHIC_DRAFT_SYSTEM = """\
You are designing a single-page infographic layout. Output must conform
to the Infographic schema.

Rules:
- Title is a short, bold headline (≤10 words).
- Subtitle explains the title in one sentence.
- Lede is the single most important finding, phrased as one complete sentence.
- stats contains 3-4 headline numbers pulled directly from the source. Each
  has a short label and optional caveat (e.g. 'pilot only', 'year-over-year').
  NEVER fabricate numbers that are not in the source.
- sections contains 3-5 supporting themes, each with a short heading,
  40-240 characters of body, and an icon_hint from:
  chart | shield | clock | people | spark | flag | lightning | globe | check.
- takeaway is a one-line conclusion printed in the footer banner.
- Pick the color_theme that best fits the content's tone.
"""


@register_generator
class InfographicGenerator(BaseArtifactGenerator):
    artifact_type = "infographic"
    description = "Single-page infographic PNG + HTML with data-driven stats and takeaway."

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        theme_hint = request.config.get("color_theme", "blue")
        claims = await extract_claims(
            self.llm,
            request.combined_content(max_chars=14000),
            focus="infographic layout with headline metrics",
        )
        context = claims_to_context(claims, max_claims=25)
        info = await draft_and_refine(
            self.llm,
            schema=Infographic,
            draft_system=INFOGRAPHIC_DRAFT_SYSTEM + f"\nPreferred color_theme: {theme_hint}.",
            context=context,
            quality_floor=8,
        )
        data = info.model_dump()
        data.setdefault("title", request.title or data["title"])

        png_path = self.output_path(request, "png")
        render_infographic(data, png_path)
        html_path = self.output_path(request, "html")
        render_infographic_html(data, html_path)
        json_path = self.output_path(request, "json")
        json_path.write_text(info.model_dump_json(indent=2), encoding="utf-8")

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=data["title"],
            summary=data.get("lede"),
            structured=data,
            files=[
                ArtifactFile(path=str(png_path), mime_type="image/png",
                             description="Infographic (PNG)"),
                ArtifactFile(path=str(html_path), mime_type="text/html",
                             description="Infographic (HTML)"),
                ArtifactFile(path=str(json_path), mime_type="application/json"),
            ],
            metadata={
                "stat_count": len(data.get("stats", [])),
                "section_count": len(data.get("sections", [])),
                "color_theme": data.get("color_theme"),
            },
        )
