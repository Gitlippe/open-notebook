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
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


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

    def combined_content(self, max_chars: Optional[int] = None) -> str:
        """Concatenate sources into a single context string."""
        parts = [src.to_context_block() for src in self.sources]
        joined = "\n\n---\n\n".join(parts)
        if max_chars and len(joined) > max_chars:
            joined = joined[:max_chars] + "\n\n[... content truncated ...]"
        return joined

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
    """Output payload returned by any artifact generator."""

    artifact_type: str
    title: str
    summary: Optional[str] = None
    structured: Dict[str, Any] = Field(default_factory=dict)
    files: List[ArtifactFile] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
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

    def __init__(self, llm: Optional[Any] = None) -> None:
        """Create a generator.

        ``llm`` should be an :class:`ArtifactLLM` or any object exposing a
        ``.generate_json()`` / ``.generate_text()`` API. When omitted, each
        generator will lazily instantiate the default :class:`ArtifactLLM`,
        which automatically falls back to a deterministic heuristic model
        when no AI provider is configured.
        """
        self._llm = llm

    @property
    def llm(self):
        if self._llm is None:
            from open_notebook.artifacts.llm import ArtifactLLM

            self._llm = ArtifactLLM()
        return self._llm

    def output_dir(self, request: ArtifactRequest) -> Path:
        """Ensure the output directory exists and return it."""
        base = Path(request.output_dir or ".artifact_output")
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

    @abc.abstractmethod
    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        """Implementations must return a fully-populated ``ArtifactResult``."""
