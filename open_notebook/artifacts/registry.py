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
    generator = get_generator(artifact_type, llm=llm)
    return await generator.generate(request)


def _autoregister() -> None:
    """Import built-in generators to populate the registry.

    Two sentinel regions — one per workstream — prevent merge conflicts
    when parallel agents add generators. Stream B owns BATCH_B, Stream C
    owns BATCH_C. Alphabetise within each region.
    """
    # <BATCH B>
    from open_notebook.artifacts.generators import (  # noqa: F401
        briefing,
        faq,
        flashcards,
        mindmap,
        quiz,
        study_guide,
        timeline,
    )
    # </BATCH B>

    # <BATCH C>
    from open_notebook.artifacts.generators import (  # noqa: F401
        data_tables,
        infographic,
        paper_figure,
        pitch_deck,
        research_review,
        slide_deck,
        video_overview,
    )
    # </BATCH C>


_autoregister()
