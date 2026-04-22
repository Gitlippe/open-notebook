"""Quiz (MCQ) artifact generator.

Uses ``chunked_generate`` + provider-native structured output to produce a
fully-validated ``QuizSchema`` instance. No heuristic fallback.
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
from open_notebook.artifacts.prompts import build_quiz_prompt
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers import markdown as md


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------


class QuizQuestionSchema(BaseModel):
    """A single multiple-choice question."""

    question: str = Field(..., description="Clear, single-focus question")
    options: List[str] = Field(..., description="Exactly 4 answer options")
    answer_index: int = Field(..., description="0-based index of the correct option (0-3)")
    explanation: str = Field(..., description="Why the correct option is correct")


class QuizSchema(BaseModel):
    """Validated output of a quiz artifact."""

    title: str = Field(..., description="Quiz: <topic>")
    questions: List[QuizQuestionSchema] = Field(
        ..., description="5-10 multiple-choice questions"
    )


# ---------------------------------------------------------------------------
# Markdown renderer (local to this module)
# ---------------------------------------------------------------------------


def _render_quiz_markdown(data: dict) -> str:
    lines = [f"# {data.get('title', 'Quiz')}", ""]
    for idx, q in enumerate(data.get("questions", []), start=1):
        lines.append(f"### Q{idx}. {q.get('question', '')}")
        for opt_idx, opt in enumerate(q.get("options", [])):
            marker = " **(correct)**" if opt_idx == q.get("answer_index") else ""
            lines.append(f"- [{chr(65 + opt_idx)}] {opt}{marker}")
        expl = q.get("explanation")
        if expl:
            lines.append("")
            lines.append(f"*Explanation:* {expl}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


@register_generator
class QuizGenerator(BaseArtifactGenerator):
    """Multiple-choice quiz with options, answers, and explanations."""

    artifact_type = "quiz"
    description = "Multiple-choice quiz with options, answers, and explanations."
    default_model_type = "transformation"

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        question_count: int = int(request.config.get("question_count", 6))
        instructions = build_quiz_prompt(question_count=question_count)

        def map_prompt(chunk: str) -> str:
            return combine_prompts(instructions, chunk)

        def reduce_prompt(partials: list) -> str:
            all_qs = []
            for p in partials:
                for q in p.questions:
                    opts = " | ".join(
                        f"[{chr(65+i)}] {o}" for i, o in enumerate(q.options)
                    )
                    all_qs.append(
                        f"Q: {q.question}\n{opts}\nAnswer: {chr(65 + q.answer_index)}\n"
                        f"Explanation: {q.explanation}"
                    )
            combined_text = "\n\n---\n\n".join(all_qs)
            synthesis_instructions = (
                build_quiz_prompt(question_count=question_count)
                + "\n\nYou are consolidating questions extracted from multiple source chunks. "
                "Remove duplicate or near-duplicate questions. Keep the best "
                f"{question_count} with varied difficulty (recall, application, analysis)."
            )
            return combine_prompts(synthesis_instructions, combined_text)

        result: QuizSchema = await self.chunked_generate(
            request,
            schema=QuizSchema,
            map_prompt_builder=map_prompt,
            reduce_prompt_builder=reduce_prompt,
        )

        title = result.title or request.title or "Quiz"
        data = result.model_dump()
        data["title"] = title

        md_path = self.output_path(request, "md")
        md.write(md_path, _render_quiz_markdown(data))

        json_path = self.output_path(request, "json")
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=title,
            summary=f"{len(result.questions)} questions",
            structured=data,
            files=[
                ArtifactFile(
                    path=str(md_path),
                    mime_type="text/markdown",
                    description="Quiz (Markdown)",
                ),
                ArtifactFile(
                    path=str(json_path),
                    mime_type="application/json",
                    description="Structured JSON",
                ),
            ],
            provenance=self.llm.provenance,
            metadata={"question_count": len(result.questions)},
        )
