"""Timeline artifact generator (structured JSON + PNG via matplotlib).

Uses ``chunked_generate`` + provider-native structured output to produce a
fully-validated ``TimelineSchema`` instance. No heuristic fallback.
"""
from __future__ import annotations

import json
from typing import List

from pydantic import BaseModel, Field

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.llm import combine_prompts
from open_notebook.artifacts.prompts import build_timeline_prompt
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers.chart_renderer import render_timeline


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------


class TimelineEventSchema(BaseModel):
    """A single chronological event."""

    date: str = Field(
        ..., description="ISO date or free-form year/period (e.g. '2023-10', 'Early 2024')"
    )
    event: str = Field(..., description="What happened — one clear, specific sentence")
    significance: str = Field(
        ..., description="Why this event matters in context"
    )


class TimelineSchema(BaseModel):
    """Validated output of a timeline artifact."""

    title: str = Field(..., description="Timeline: <topic>")
    events: List[TimelineEventSchema] = Field(
        ..., description="5-15 chronological events, earliest first"
    )


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


@register_generator
class TimelineGenerator(BaseArtifactGenerator):
    """Chronological timeline rendered as a PNG with markdown and JSON."""

    artifact_type = "timeline"
    description = "Chronological timeline rendered as a PNG with markdown summary."
    default_model_type = "transformation"

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        instructions = build_timeline_prompt()

        def map_prompt(chunk: str) -> str:
            return combine_prompts(instructions, chunk)

        def reduce_prompt(partials: list) -> str:
            all_events = []
            for p in partials:
                for ev in p.events:
                    all_events.append(
                        f"Date: {ev.date}\nEvent: {ev.event}\nSignificance: {ev.significance}"
                    )
            combined_text = "\n\n---\n\n".join(all_events)
            synthesis_instructions = (
                build_timeline_prompt()
                + "\n\nYou are consolidating timeline events from multiple source chunks. "
                "Remove duplicate or near-duplicate events. Order chronologically. "
                "Keep 5-15 of the most significant events."
            )
            return combine_prompts(synthesis_instructions, combined_text)

        result: TimelineSchema = await self.chunked_generate(
            request,
            schema=TimelineSchema,
            map_prompt_builder=map_prompt,
            reduce_prompt_builder=reduce_prompt,
        )

        title = result.title or request.title or "Timeline"
        data = result.model_dump()
        data["title"] = title

        # Normalise for chart_renderer which expects {date, event} fields
        chart_data = {
            "title": title,
            "events": [
                {"date": ev["date"], "event": ev["event"]}
                for ev in data["events"]
            ],
        }

        json_path = self.output_path(request, "json")
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        md_path = self.output_path(request, "md")
        md_lines = [f"# {title}", ""]
        for ev in result.events:
            md_lines.append(f"- **{ev.date}** — {ev.event}")
            if ev.significance:
                md_lines.append(f"  > {ev.significance}")
        md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

        png_path = self.output_path(request, "png")
        render_timeline(chart_data, png_path)

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=title,
            summary=f"{len(result.events)} events",
            structured=data,
            files=[
                ArtifactFile(
                    path=str(png_path),
                    mime_type="image/png",
                    description="Timeline (PNG)",
                ),
                ArtifactFile(
                    path=str(md_path),
                    mime_type="text/markdown",
                    description="Timeline (Markdown)",
                ),
                ArtifactFile(
                    path=str(json_path),
                    mime_type="application/json",
                    description="Structured JSON",
                ),
            ],
            provenance=self.llm.provenance,
            metadata={"event_count": len(result.events)},
        )
