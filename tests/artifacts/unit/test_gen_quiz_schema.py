"""Unit tests for QuizGenerator — schema, registry, and model-type checks.

No real LLM calls. Tests verify:
1. QuizSchema / QuizQuestionSchema have required fields.
2. QuizGenerator is registered in ARTIFACT_TYPES.
3. QuizGenerator.default_model_type is set.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_quiz_schema_required_fields() -> None:
    """QuizSchema must expose title and questions."""
    from open_notebook.artifacts.generators.quiz import QuizSchema

    schema_fields = set(QuizSchema.model_fields.keys())
    required = {"title", "questions"}
    missing = required - schema_fields
    assert not missing, (
        f"QuizSchema is missing required fields: {missing}. Present: {schema_fields}"
    )


def test_quiz_question_schema_required_fields() -> None:
    """QuizQuestionSchema must have question, options, answer_index, explanation."""
    from open_notebook.artifacts.generators.quiz import QuizQuestionSchema

    q_fields = set(QuizQuestionSchema.model_fields.keys())
    required = {"question", "options", "answer_index", "explanation"}
    missing = required - q_fields
    assert not missing, (
        f"QuizQuestionSchema is missing required fields: {missing}. Present: {q_fields}"
    )


def test_quiz_schema_instantiation() -> None:
    """QuizSchema must be constructible with valid nested data."""
    from open_notebook.artifacts.generators.quiz import QuizQuestionSchema, QuizSchema

    obj = QuizSchema(
        title="Quiz: Transformers",
        questions=[
            QuizQuestionSchema(
                question="What operation produces attention scores?",
                options=[
                    "Element-wise addition",
                    "Query-key dot product followed by softmax",
                    "Convolutional filter application",
                    "Layer normalisation",
                ],
                answer_index=1,
                explanation="Attention scores are computed as softmax(QK^T / sqrt(d_k)).",
            )
        ],
    )
    assert obj.title == "Quiz: Transformers"
    assert len(obj.questions) == 1
    assert obj.questions[0].answer_index == 1
    dumped = obj.model_dump()
    assert len(dumped["questions"][0]["options"]) == 4


def test_quiz_generator_in_registry() -> None:
    """QuizGenerator must be registered in ARTIFACT_TYPES."""
    from open_notebook.artifacts.registry import ARTIFACT_TYPES

    assert "quiz" in ARTIFACT_TYPES, (
        f"'quiz' not in ARTIFACT_TYPES. Registered: {sorted(ARTIFACT_TYPES.keys())}"
    )


def test_quiz_generator_default_model_type() -> None:
    """QuizGenerator.default_model_type must be a non-empty string."""
    from open_notebook.artifacts.generators.quiz import QuizGenerator

    assert QuizGenerator.default_model_type, (
        "QuizGenerator.default_model_type must be set."
    )
    assert isinstance(QuizGenerator.default_model_type, str)


def test_quiz_generator_uses_chunked_generate() -> None:
    """QuizGenerator.generate must call chunked_generate."""
    import inspect

    from open_notebook.artifacts.generators.quiz import QuizGenerator

    source = inspect.getsource(QuizGenerator.generate)
    assert "chunked_generate" in source, (
        "QuizGenerator.generate must call self.chunked_generate()."
    )
    assert "generate_json" not in source, (
        "QuizGenerator must not use generate_json (legacy)."
    )
