"""Quiz (MCQ) artifact generator."""
from __future__ import annotations

import json

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.llm import combine_prompts
from open_notebook.artifacts.prompts import QUIZ_PROMPT
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers import markdown as md


def _render_markdown(data) -> str:
    lines = [f"# {data.get('title', 'Quiz')}", ""]
    for idx, q in enumerate(data.get("questions", []), start=1):
        lines.append(f"### Q{idx}. {q.get('question', '')}")
        for opt_idx, opt in enumerate(q.get("options", [])):
            marker = "(correct)" if opt_idx == q.get("answer_index") else ""
            lines.append(f"- [{chr(65 + opt_idx)}] {opt} {marker}".rstrip())
        expl = q.get("explanation")
        if expl:
            lines.append("")
            lines.append(f"*Explanation:* {expl}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


@register_generator
class QuizGenerator(BaseArtifactGenerator):
    artifact_type = "quiz"
    description = "Multiple-choice quiz with options, answers, and explanations."

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        n_questions = request.config.get("question_count", 6)
        directive = QUIZ_PROMPT + f"\nTarget ~{n_questions} questions."
        prompt = combine_prompts(directive, request.combined_content(max_chars=14000))
        data = await self.llm.generate_json(
            prompt, artifact_type=self.artifact_type
        )
        data.setdefault("title", request.title or "Quiz")

        md_path = self.output_path(request, "md")
        md.write(md_path, _render_markdown(data))
        json_path = self.output_path(request, "json")
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=data["title"],
            summary=f"{len(data.get('questions', []))} questions",
            structured=data,
            files=[
                ArtifactFile(path=str(md_path), mime_type="text/markdown"),
                ArtifactFile(path=str(json_path), mime_type="application/json"),
            ],
            metadata={"question_count": len(data.get("questions", []))},
        )
