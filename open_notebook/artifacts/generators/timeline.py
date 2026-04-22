"""Timeline artifact generator with canonicalised event dates."""
from __future__ import annotations

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers.chart_renderer import render_timeline
from open_notebook.artifacts.schemas import Timeline
from open_notebook.artifacts.workflow import (
    claims_to_context,
    draft_and_refine,
    extract_claims,
)

TIMELINE_DRAFT_SYSTEM = """\
You are extracting a chronological timeline from the source material.
Output must conform to the Timeline schema.

Rules:
- 5-15 events. Only include events with concrete dates (a year minimum).
- date field: ISO 8601 where possible (YYYY, YYYY-MM, YYYY-MM-DD).
- event is a one-sentence factual description grounded in the source.
- category is a short tag like 'release', 'research', 'business', 'policy'.
- importance is 'major' for turning points, 'minor' for supporting context.
- Order events earliest to latest.
"""


@register_generator
class TimelineGenerator(BaseArtifactGenerator):
    artifact_type = "timeline"
    description = "Chronological timeline with canonicalised dates and importance tiers."

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        claims = await extract_claims(
            self.llm,
            request.combined_content(max_chars=16000),
            focus="dated events",
        )
        context = claims_to_context(claims, max_claims=25)
        timeline = await draft_and_refine(
            self.llm,
            schema=Timeline,
            draft_system=TIMELINE_DRAFT_SYSTEM,
            context=context,
            quality_floor=7,
        )
        data = timeline.model_dump()
        data.setdefault("title", request.title or data["title"])
        data["events"] = sorted(data["events"], key=lambda e: e["date"])

        json_path = self.output_path(request, "json")
        json_path.write_text(timeline.model_dump_json(indent=2), encoding="utf-8")
        md_path = self.output_path(request, "md")
        md_lines = [f"# {data['title']}", ""]
        for ev in data["events"]:
            tag = f" [{ev.get('category')}]" if ev.get("category") else ""
            md_lines.append(f"- **{ev['date']}**{tag} — {ev['event']}")
        md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
        png_path = self.output_path(request, "png")
        render_timeline(data, png_path)

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=data["title"],
            summary=f"{len(data['events'])} events, {sum(1 for e in data['events'] if e.get('importance') == 'major')} major",
            structured=data,
            files=[
                ArtifactFile(path=str(png_path), mime_type="image/png",
                             description="Timeline (PNG)"),
                ArtifactFile(path=str(md_path), mime_type="text/markdown"),
                ArtifactFile(path=str(json_path), mime_type="application/json"),
            ],
            metadata={
                "event_count": len(data["events"]),
                "major_count": sum(1 for e in data["events"] if e.get("importance") == "major"),
            },
        )
