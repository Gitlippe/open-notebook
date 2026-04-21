"""FAQ artifact generator."""
from __future__ import annotations

import json

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.llm import combine_prompts
from open_notebook.artifacts.prompts import FAQ_PROMPT
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers import markdown as md


@register_generator
class FAQGenerator(BaseArtifactGenerator):
    artifact_type = "faq"
    description = "Frequently asked questions and concise answers derived from sources."

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        prompt = combine_prompts(FAQ_PROMPT, request.combined_content(max_chars=14000))
        data = await self.llm.generate_json(
            prompt, artifact_type=self.artifact_type
        )
        data.setdefault("title", request.title or "FAQ")

        md_path = self.output_path(request, "md")
        md.write(md_path, md.render_faq(data))
        json_path = self.output_path(request, "json")
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        items = data.get("items", [])
        summary = items[0]["answer"] if items else None

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=data["title"],
            summary=summary,
            structured=data,
            files=[
                ArtifactFile(path=str(md_path), mime_type="text/markdown",
                             description="FAQ (Markdown)"),
                ArtifactFile(path=str(json_path), mime_type="application/json"),
            ],
            metadata={"item_count": len(items)},
        )
