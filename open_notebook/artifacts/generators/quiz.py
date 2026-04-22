"""Quiz generator with Bloom-diverse questions and high-quality distractors."""
from __future__ import annotations

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.registry import register_generator
from open_notebook.artifacts.renderers import markdown as md
from open_notebook.artifacts.schemas import Quiz
from open_notebook.artifacts.workflow import (
    claims_to_context,
    draft_and_refine,
    extract_claims,
)


def _render_markdown(data: dict) -> str:
    lines = [f"# {data.get('title', 'Quiz')}", ""]
    for idx, q in enumerate(data.get("questions", []), start=1):
        meta = f"_[{q['bloom_level']} · {q['difficulty']}]_"
        lines.append(f"### Q{idx}. {q['question']}")
        lines.append(meta)
        for opt_idx, opt in enumerate(q["options"]):
            marker = "(correct)" if opt_idx == q["answer_index"] else ""
            lines.append(f"- [{chr(65 + opt_idx)}] {opt} {marker}".rstrip())
        lines.append("")
        lines.append(f"*Explanation:* {q['explanation']}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


QUIZ_DRAFT_SYSTEM = """\
You are creating a multiple-choice quiz grounded in the source material.
Output must conform to the Quiz schema.

Rules:
- 5-10 questions. Each has exactly 4 options.
- Distractors (wrong options) must be plausible. No joke answers. They
  should represent common misunderstandings or near-misses drawn from
  content adjacent to the correct answer.
- Each question has a bloom_level and difficulty. The set must span at
  least three bloom levels and include easy, medium, and hard.
- answer_index is a 0-based integer that indexes the options list.
- Explanations state why the correct answer is correct AND briefly name
  why the most tempting distractor is wrong.
- Every question's content must be grounded in the claim set.
"""


@register_generator
class QuizGenerator(BaseArtifactGenerator):
    artifact_type = "quiz"
    description = "Bloom-diverse MCQ quiz with plausible distractors and explanations."

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        n = request.config.get("question_count", 6)
        claims = await extract_claims(
            self.llm,
            request.combined_content(max_chars=14000),
            focus=f"~{n} MCQ questions",
        )
        context = claims_to_context(claims, max_claims=20)
        quiz = await draft_and_refine(
            self.llm,
            schema=Quiz,
            draft_system=QUIZ_DRAFT_SYSTEM + f"\nTarget {n} questions.",
            context=context,
            quality_floor=8,
        )
        data = quiz.model_dump()
        data.setdefault("title", request.title or data["title"])

        md_path = self.output_path(request, "md")
        md.write(md_path, _render_markdown(data))
        json_path = self.output_path(request, "json")
        json_path.write_text(quiz.model_dump_json(indent=2), encoding="utf-8")

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=data["title"],
            summary=f"{len(data['questions'])} questions spanning "
                    f"{len({q['bloom_level'] for q in data['questions']})} Bloom levels",
            structured=data,
            files=[
                ArtifactFile(path=str(md_path), mime_type="text/markdown"),
                ArtifactFile(path=str(json_path), mime_type="application/json"),
            ],
            metadata={
                "question_count": len(data["questions"]),
                "bloom_levels": sorted({q["bloom_level"] for q in data["questions"]}),
                "difficulty_mix": sorted({q["difficulty"] for q in data["questions"]}),
            },
        )
