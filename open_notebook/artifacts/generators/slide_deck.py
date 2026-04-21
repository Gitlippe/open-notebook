"""Informational slide deck generator (.pptx)."""
from __future__ import annotations

import json

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.llm import combine_prompts
from open_notebook.artifacts.prompts import SLIDE_DECK_PROMPT
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers.pptx_renderer import render_deck


def _render_markdown(data) -> str:
    lines = [f"# {data.get('title', 'Deck')}"]
    if data.get("subtitle"):
        lines.append(f"_{data['subtitle']}_")
    for idx, slide in enumerate(data.get("slides", []), start=1):
        lines.append("")
        lines.append(f"## Slide {idx}: {slide.get('title', '')}")
        for bullet in slide.get("bullets", []):
            lines.append(f"- {bullet}")
        if slide.get("notes"):
            lines.append("")
            lines.append(f"> {slide['notes']}")
    return "\n".join(lines).strip() + "\n"


@register_generator
class SlideDeckGenerator(BaseArtifactGenerator):
    artifact_type = "slide_deck"
    description = "Informational slide deck rendered as .pptx with speaker notes."

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        target = request.config.get("length", "standard")
        directive = SLIDE_DECK_PROMPT + f"\nTarget length: {target}."
        prompt = combine_prompts(directive, request.combined_content(max_chars=18000))
        data = await self.llm.generate_json(
            prompt, artifact_type=self.artifact_type
        )
        data.setdefault("title", request.title or "Slide Deck")

        pptx_path = self.output_path(request, "pptx")
        render_deck(data, pptx_path)

        md_path = self.output_path(request, "md")
        md_path.write_text(_render_markdown(data), encoding="utf-8")

        json_path = self.output_path(request, "json")
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=data["title"],
            summary=data.get("subtitle"),
            structured=data,
            files=[
                ArtifactFile(
                    path=str(pptx_path),
                    mime_type=(
                        "application/vnd.openxmlformats-officedocument"
                        ".presentationml.presentation"
                    ),
                    description="Slide deck (.pptx)",
                ),
                ArtifactFile(path=str(md_path), mime_type="text/markdown"),
                ArtifactFile(path=str(json_path), mime_type="application/json"),
            ],
            metadata={"slide_count": len(data.get("slides", []))},
        )
