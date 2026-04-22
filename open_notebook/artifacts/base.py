"""Base contracts for artifact generators.

This module defines the shared request, response, and base generator classes
used by every artifact type. Keeping them in one place makes it trivial to
add new artifact types (see ``registry.py``).
"""
from __future__ import annotations

import abc
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel, Field

from open_notebook.artifacts.llm import ArtifactLLM, GenerationProvenance


TModel = TypeVar("TModel", bound=BaseModel)


class ArtifactSource(BaseModel):
    """A single piece of input content feeding an artifact generator."""

    title: str = Field(..., description="Source title or identifier")
    content: str = Field(..., description="Raw text content of the source")
    url: Optional[str] = Field(None, description="Original URL, if any")
    author: Optional[str] = Field(None, description="Author or origin")
    published_at: Optional[str] = Field(None, description="Publication date, free-form")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_context_block(self) -> str:
        """Render the source as a prompt-ready text block."""
        header_bits: list[str] = [f"SOURCE: {self.title}"]
        if self.author:
            header_bits.append(f"AUTHOR: {self.author}")
        if self.published_at:
            header_bits.append(f"DATE: {self.published_at}")
        if self.url:
            header_bits.append(f"URL: {self.url}")
        return "\n".join(header_bits) + "\n\n" + self.content.strip()


class ArtifactRequest(BaseModel):
    """Input payload for any artifact generator.

    The generator-specific knobs (tone, length, audience, etc.) live inside
    ``config`` so that a single request schema can serve every artifact type.
    """

    artifact_type: str = Field(..., description="e.g. 'briefing', 'slide_deck'")
    title: Optional[str] = Field(None, description="Optional artifact title")
    sources: List[ArtifactSource] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)
    model_id: Optional[str] = Field(None, description="LLM model override")
    output_dir: Optional[str] = Field(
        None, description="Directory for rendered artifact files"
    )

    def combined_content(self) -> str:
        """Concatenate sources into a single full-fidelity context string.

        NOTE: This no longer truncates. Long inputs must flow through
        :meth:`BaseArtifactGenerator.chunked_generate` for map-reduce
        summarisation instead of silent truncation. A lint test blocks
        any callsite that tries to reintroduce the old ``max_chars``
        parameter (see tests/artifacts/unit/test_no_heuristic.py).
        """
        parts = [src.to_context_block() for src in self.sources]
        return "\n\n---\n\n".join(parts)

    def fingerprint(self) -> str:
        """Stable short hash used for output filenames."""
        payload = json.dumps(
            {
                "type": self.artifact_type,
                "title": self.title,
                "sources": [
                    {"t": s.title, "c": s.content[:200]} for s in self.sources
                ],
                "config": self.config,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]


class ArtifactFile(BaseModel):
    """Metadata about a rendered file on disk."""

    path: str
    mime_type: str
    description: Optional[str] = None


class ArtifactResult(BaseModel):
    """Output payload returned by any artifact generator.

    ``provenance`` is populated by :class:`ArtifactLLM` and is the canonical
    evidence that a real LLM call backed this artifact. Tests assert
    ``len(provenance.calls) >= 1``.
    """

    artifact_type: str
    title: str
    summary: Optional[str] = None
    structured: Dict[str, Any] = Field(default_factory=dict)
    files: List[ArtifactFile] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    provenance: Optional[GenerationProvenance] = None
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def primary_file(self) -> Optional[ArtifactFile]:
        return self.files[0] if self.files else None


class BaseArtifactGenerator(abc.ABC):
    """Abstract base class for every artifact type."""

    #: Unique artifact-type identifier, e.g. ``"briefing"``.
    artifact_type: str = ""
    #: Human-readable short description for registry listings.
    description: str = ""
    #: Model-type key passed to ``provision_langchain_model`` (e.g.
    #: ``"transformation"``, ``"chat"``, ``"tools"``). Override per generator
    #: if a different default pool should serve this artifact.
    default_model_type: str = "transformation"
    #: Hard cap on input tokens before chunked_generate() fans out.
    #: Models with larger context will still work — this just controls
    #: when we switch to map-reduce.
    chunk_threshold_tokens: int = 100_000

    def __init__(self, llm: Optional[ArtifactLLM] = None) -> None:
        """Create a generator.

        ``llm`` should be an :class:`ArtifactLLM` (or a test double). When
        omitted, the generator lazily instantiates a fresh ``ArtifactLLM``
        bound to this generator's ``artifact_type``.
        """
        self._llm = llm

    @property
    def llm(self) -> ArtifactLLM:
        if self._llm is None:
            self._llm = ArtifactLLM(
                default_type=self.default_model_type,
                artifact_type=self.artifact_type,
            )
        return self._llm

    def output_dir(self, request: ArtifactRequest) -> Path:
        """Ensure the output directory exists and return it."""
        from open_notebook.config import ARTIFACT_OUTPUT_ROOT

        base = Path(request.output_dir) if request.output_dir else Path(ARTIFACT_OUTPUT_ROOT)
        base.mkdir(parents=True, exist_ok=True)
        return base

    def output_path(
        self,
        request: ArtifactRequest,
        extension: str,
        suffix: str = "",
    ) -> Path:
        fingerprint = request.fingerprint()
        stem = (request.title or self.artifact_type).lower()
        stem = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in stem)
        name = f"{stem}_{fingerprint}"
        if suffix:
            name += f"_{suffix}"
        return self.output_dir(request) / f"{name}.{extension.lstrip('.')}"

    # ------------------------------------------------------------------
    # Long-input handling
    # ------------------------------------------------------------------
    async def chunked_generate(
        self,
        request: ArtifactRequest,
        *,
        schema: Type[TModel],
        map_prompt_builder: Callable[[str], str],
        reduce_prompt_builder: Callable[[List[TModel]], str],
    ) -> TModel:
        """Map-reduce path for long-context artifact generation.

        1. If combined content fits in the configured threshold, run a single
           structured call on the whole thing.
        2. Otherwise, chunk via :func:`open_notebook.utils.chunking.chunk_text`,
           run ``map_prompt_builder(chunk)`` against each chunk (in parallel),
           then ``reduce_prompt_builder(intermediate_results)`` for the final
           synthesis.

        The schema is applied at BOTH stages so intermediate results are also
        validated Pydantic instances — never free-form JSON chatter.
        """
        from open_notebook.utils import token_count
        from open_notebook.utils.chunking import chunk_text

        content = request.combined_content()
        tokens = token_count(content)

        if tokens <= self.chunk_threshold_tokens:
            return await self.llm.generate_structured(
                map_prompt_builder(content), schema
            )

        # Long input — fan out chunk-by-chunk.
        chunks = chunk_text(content)
        import asyncio

        intermediate = await asyncio.gather(
            *[
                self.llm.generate_structured(map_prompt_builder(chunk), schema)
                for chunk in chunks
            ]
        )
        return await self.llm.generate_structured(
            reduce_prompt_builder(intermediate), schema
        )

    @abc.abstractmethod
    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        """Implementations must return a fully-populated ``ArtifactResult``
        including non-empty ``provenance.calls``.
        """
