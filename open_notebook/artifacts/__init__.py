"""Artifact generation package for Open Notebook.

Provides a modular, pluggable system for generating multiple artifact types
from research sources: briefings (BLUF summaries), study guides, FAQs,
research reviews, flashcards, quizzes, mind maps, timelines, infographics,
slide decks, pitch decks, and paper figures.

Each artifact is a subclass of :class:`BaseArtifactGenerator` that consumes
an :class:`ArtifactRequest` and produces an :class:`ArtifactResult`.

High-level API::

    from open_notebook.artifacts import generate_artifact

    result = await generate_artifact(
        artifact_type="briefing",
        sources=[{"title": "...", "content": "..."}],
        config={"audience": "executive"},
        output_dir="/tmp/out",
    )
"""
from open_notebook.artifacts.base import (
    ArtifactRequest,
    ArtifactResult,
    ArtifactSource,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.registry import (
    ARTIFACT_TYPES,
    generate_artifact,
    get_generator,
    list_artifact_types,
    register_generator,
)

__all__ = [
    "ArtifactRequest",
    "ArtifactResult",
    "ArtifactSource",
    "ARTIFACT_TYPES",
    "BaseArtifactGenerator",
    "generate_artifact",
    "get_generator",
    "list_artifact_types",
    "register_generator",
]
