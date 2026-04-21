"""Pitch deck generator (venture-style) — a specialised slide deck."""
from __future__ import annotations

import json

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.llm import combine_prompts
from open_notebook.artifacts.prompts import PITCH_DECK_PROMPT
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers.pptx_renderer import render_deck


def _render_markdown(data) -> str:
    lines = [f"# {data.get('title', 'Pitch Deck')}"]
    if data.get("tagline"):
        lines.append(f"_{data['tagline']}_")
    for idx, slide in enumerate(data.get("slides", []), start=1):
        lines.append("")
        lines.append(f"## {idx}. {slide.get('title', '')}")
        for bullet in slide.get("bullets", []):
            lines.append(f"- {bullet}")
        if slide.get("notes"):
            lines.append("")
            lines.append(f"> {slide['notes']}")
    return "\n".join(lines).strip() + "\n"


@register_generator
class PitchDeckGenerator(BaseArtifactGenerator):
    artifact_type = "pitch_deck"
    description = "Investor-style pitch deck (.pptx) with canonical VC structure."

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        company = request.config.get("company", request.title or "Your Company")
        directive = PITCH_DECK_PROMPT + f"\nCompany/Product: {company}."
        prompt = combine_prompts(directive, request.combined_content(max_chars=18000))
        data = await self.llm.generate_json(
            prompt, artifact_type=self.artifact_type
        )
        data.setdefault("title", company)

        pptx_path = self.output_path(request, "pptx")

        prep = dict(data)
        prep.setdefault("subtitle", data.get("tagline"))
        render_deck(prep, pptx_path)

        md_path = self.output_path(request, "md")
        md_path.write_text(_render_markdown(data), encoding="utf-8")

        json_path = self.output_path(request, "json")
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=data["title"],
            summary=data.get("tagline"),
            structured=data,
            files=[
                ArtifactFile(
                    path=str(pptx_path),
                    mime_type=(
                        "application/vnd.openxmlformats-officedocument"
                        ".presentationml.presentation"
                    ),
                    description="Pitch deck (.pptx)",
                ),
                ArtifactFile(path=str(md_path), mime_type="text/markdown"),
                ArtifactFile(path=str(json_path), mime_type="application/json"),
            ],
            metadata={
                "slide_count": len(data.get("slides", [])),
                "company": company,
            },
        )
