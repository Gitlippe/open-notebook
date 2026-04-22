"""Central registry of artifact generators."""
from __future__ import annotations

from typing import Dict, List, Optional, Type

from open_notebook.artifacts.base import (
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)

#: Runtime-mutable mapping of artifact-type → generator class.
ARTIFACT_TYPES: Dict[str, Type[BaseArtifactGenerator]] = {}


def register_generator(cls: Type[BaseArtifactGenerator]) -> Type[BaseArtifactGenerator]:
    if not cls.artifact_type:
        raise ValueError(f"{cls.__name__} is missing an artifact_type")
    ARTIFACT_TYPES[cls.artifact_type] = cls
    return cls


def list_artifact_types() -> List[Dict[str, str]]:
    return [
        {"type": cls.artifact_type, "description": cls.description}
        for cls in ARTIFACT_TYPES.values()
    ]


def get_generator(artifact_type: str, llm=None) -> BaseArtifactGenerator:
    if artifact_type not in ARTIFACT_TYPES:
        raise KeyError(
            f"Unknown artifact type '{artifact_type}'. "
            f"Known: {sorted(ARTIFACT_TYPES)}"
        )
    return ARTIFACT_TYPES[artifact_type](llm=llm)


async def generate_artifact(
    artifact_type: str,
    sources,
    config: Optional[Dict[str, object]] = None,
    title: Optional[str] = None,
    model_id: Optional[str] = None,
    output_dir: Optional[str] = None,
    llm=None,
    use_mock_if_unavailable: bool = True,
) -> ArtifactResult:
    """Convenience one-shot generator.

    ``sources`` may be a list of :class:`ArtifactSource`, dicts, or (title,
    content) tuples.
    """
    from open_notebook.artifacts.base import ArtifactSource

    if not sources:
        raise ValueError(
            f"At least one source is required to generate artifact '{artifact_type}'."
        )

    normalised = []
    for src in sources:
        if isinstance(src, ArtifactSource):
            normalised.append(src)
        elif isinstance(src, dict):
            normalised.append(ArtifactSource(**src))
        elif isinstance(src, (list, tuple)) and len(src) == 2:
            normalised.append(ArtifactSource(title=src[0], content=src[1]))
        else:
            raise TypeError(f"Unsupported source type: {type(src)!r}")

    request = ArtifactRequest(
        artifact_type=artifact_type,
        title=title,
        sources=normalised,
        config=config or {},
        model_id=model_id,
        output_dir=output_dir,
    )

    # LLM resolution: if caller did not pass one and no provider is
    # configured, auto-wire a StructuredMockChat-backed ArtifactLLM so the
    # multi-step pipeline still runs end-to-end. This keeps the offline
    # code path identical to production (same schemas, same critique loop).
    if llm is None and use_mock_if_unavailable:
        from open_notebook.artifacts.llm import ArtifactLLM, _has_provider_configured
        from open_notebook.artifacts.mock_llm import StructuredMockChat
        if not _has_provider_configured():
            llm = ArtifactLLM(chat=StructuredMockChat())

    generator = get_generator(artifact_type, llm=llm)
    return await generator.generate(request)


def _autoregister() -> None:
    """Import built-in generators to populate the registry."""
    from open_notebook.artifacts.generators import (  # noqa: F401
        briefing,
        faq,
        flashcards,
        infographic,
        mindmap,
        paper_figure,
        pitch_deck,
        quiz,
        research_review,
        slide_deck,
        study_guide,
        timeline,
    )


_autoregister()
