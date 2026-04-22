"""Paper figure generator (publication-ready chart + caption).

Schema-first, SOTA implementation using structured output via
``chunked_generate``. Selects the simplest chart type that communicates
the core result and renders it via matplotlib.
"""
from __future__ import annotations

import json
from typing import Any, List, Literal, Optional, Union

from pydantic import BaseModel, Field

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.llm import combine_prompts
from open_notebook.artifacts.prompts import (
    PAPER_FIGURE_MAP_PROMPT,
    PAPER_FIGURE_REDUCE_PROMPT,
)
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers.chart_renderer import render_paper_figure


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class DataPointSchema(BaseModel):
    x: Union[str, float] = Field(..., description="X-axis value (category name or numeric)")
    y: float = Field(..., description="Y-axis numeric value")


class SeriesSchema(BaseModel):
    name: str = Field(..., description="Series / legend label")
    data: List[DataPointSchema] = Field(..., description="Data points for this series")


class PaperFigureSchema(BaseModel):
    title: str = Field(..., description="Concise figure title (APA-style)")
    chart_type: Literal["bar", "line", "scatter"] = Field(
        ...,
        description="Chart type — bar for categories, line for trends, scatter for correlations",
    )
    x_label: str = Field(..., description="X-axis label (include units if applicable)")
    y_label: str = Field(..., description="Y-axis label (include units if applicable)")
    series: List[SeriesSchema] = Field(
        ...,
        description="One or more data series; each has a name and data points",
    )
    caption: str = Field(
        ...,
        description=(
            "1-2 sentence figure caption. If numeric data is not explicitly "
            "present in sources, note that placeholder values were estimated."
        ),
    )


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

@register_generator
class PaperFigureGenerator(BaseArtifactGenerator):
    artifact_type = "paper_figure"
    description = "Publication-ready figure (PNG) with structured data and caption."
    default_model_type = "transformation"

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        preferred_chart = request.config.get("chart_type")

        def map_prompt(chunk: str) -> str:
            directive = PAPER_FIGURE_MAP_PROMPT
            if preferred_chart:
                directive += f"\nPreferred chart_type: {preferred_chart}."
            return combine_prompts(directive, chunk)

        def reduce_prompt(partials: list[PaperFigureSchema]) -> str:
            combined_json = json.dumps(
                [p.model_dump() for p in partials], indent=2
            )
            directive = PAPER_FIGURE_REDUCE_PROMPT
            if preferred_chart:
                directive += f"\nPreferred chart_type: {preferred_chart}."
            return combine_prompts(directive, combined_json)

        result: PaperFigureSchema = await self.chunked_generate(
            request,
            schema=PaperFigureSchema,
            map_prompt_builder=map_prompt,
            reduce_prompt_builder=reduce_prompt,
        )

        data = result.model_dump()

        png_path = self.output_path(request, "png")
        render_paper_figure(data, png_path)

        json_path = self.output_path(request, "json")
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=result.title,
            summary=result.caption,
            structured=data,
            files=[
                ArtifactFile(
                    path=str(png_path),
                    mime_type="image/png",
                    description="Figure (PNG)",
                ),
                ArtifactFile(path=str(json_path), mime_type="application/json"),
            ],
            provenance=self.llm.provenance,
            metadata={
                "chart_type": result.chart_type,
                "series_count": len(result.series),
            },
        )
