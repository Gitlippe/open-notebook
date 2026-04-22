"""Artifact generation package for Open Notebook.

SOTA pipeline: plan → claim extraction → structured draft → self-critique →
refinement → format-specific rendering. Every generator uses the same
structured-output LLM protocol; offline runs use a mock backend that
implements the identical protocol rather than bypassing the workflow.
"""
from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    ArtifactSource,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.llm import (
    ArtifactLLM,
    ArtifactLLMError,
    DEFAULT_ARTIFACT_LLM,
    LangChainChat,
    StructuredChat,
    use_artifact_llm,
)
from open_notebook.artifacts.mock_llm import StructuredMockChat
from open_notebook.artifacts.registry import (
    ARTIFACT_TYPES,
    generate_artifact,
    get_generator,
    list_artifact_types,
    register_generator,
)

__all__ = [
    "ARTIFACT_TYPES",
    "ArtifactFile",
    "ArtifactLLM",
    "ArtifactLLMError",
    "ArtifactRequest",
    "ArtifactResult",
    "ArtifactSource",
    "BaseArtifactGenerator",
    "DEFAULT_ARTIFACT_LLM",
    "LangChainChat",
    "StructuredChat",
    "StructuredMockChat",
    "generate_artifact",
    "get_generator",
    "list_artifact_types",
    "register_generator",
    "use_artifact_llm",
]
