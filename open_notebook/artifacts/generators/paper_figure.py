"""Publication-grade paper figure generator."""
from __future__ import annotations

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers.chart_renderer import render_paper_figure
from open_notebook.artifacts.schemas import PaperFigure
from open_notebook.artifacts.workflow import (
    claims_to_context,
    draft_and_refine,
    extract_claims,
)

PAPER_FIGURE_DRAFT_SYSTEM = """\
You are designing a publication figure for a research paper based on the
source material. Output must conform to the PaperFigure schema.

Rules:
- Pick the simplest chart type that communicates the result
  (bar, grouped_bar, line, or scatter).
- Every data point must be grounded in the source numbers. If the source
  doesn't provide raw data, say so explicitly in the caption and provide
  a reasonable schematic based on the trends described.
- Use x_label and y_label that are concrete and units-aware.
- If one series is the key comparison (e.g., 'Proposed method'), set
  highlight_series to its name.
- Caption is a complete sentence describing what the figure shows.
"""


@register_generator
class PaperFigureGenerator(BaseArtifactGenerator):
    artifact_type = "paper_figure"
    description = "Publication-grade matplotlib figure with caption and series highlight."

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        preferred = request.config.get("chart_type")
        claims = await extract_claims(
            self.llm,
            request.combined_content(max_chars=16000),
            focus="publication figure with numeric data",
        )
        context = claims_to_context(claims, max_claims=25)
        draft_prompt = PAPER_FIGURE_DRAFT_SYSTEM
        if preferred:
            draft_prompt += f"\nPreferred chart_type: {preferred}."
        figure = await draft_and_refine(
            self.llm,
            schema=PaperFigure,
            draft_system=draft_prompt,
            context=context,
            quality_floor=7,
        )
        data = figure.model_dump()
        data.setdefault("title", request.title or data["title"])

        png_path = self.output_path(request, "png")
        render_paper_figure(data, png_path)
        json_path = self.output_path(request, "json")
        json_path.write_text(figure.model_dump_json(indent=2), encoding="utf-8")

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=data["title"],
            summary=data.get("caption"),
            structured=data,
            files=[
                ArtifactFile(path=str(png_path), mime_type="image/png",
                             description="Figure (PNG)"),
                ArtifactFile(path=str(json_path), mime_type="application/json"),
            ],
            metadata={
                "chart_type": data.get("chart_type"),
                "series_count": len(data.get("series", [])),
                "highlight_series": data.get("highlight_series"),
            },
        )
