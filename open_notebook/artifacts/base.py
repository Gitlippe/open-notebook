"""Base contracts for artifact generators.

Every generator inherits :class:`BaseArtifactGenerator` and consumes an
:class:`ArtifactRequest`, returning an :class:`ArtifactResult`.
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
    title: str = Field(..., description="Source title or identifier")
    content: str = Field(..., description="Raw text content of the source")
    url: Optional[str] = Field(None)
    author: Optional[str] = Field(None)
    published_at: Optional[str] = Field(None)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_context_block(self) -> str:
        header: List[str] = [f"SOURCE: {self.title}"]
        if self.author:
            header.append(f"AUTHOR: {self.author}")
        if self.published_at:
            header.append(f"DATE: {self.published_at}")
        if self.url:
            header.append(f"URL: {self.url}")
        return "\n".join(header) + "\n\n" + self.content.strip()


class ArtifactRequest(BaseModel):
    artifact_type: str
    title: Optional[str] = None
    sources: List[ArtifactSource] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)
    model_id: Optional[str] = None
    output_dir: Optional[str] = None

    def combined_content(self, max_chars: Optional[int] = None) -> str:
        parts = [src.to_context_block() for src in self.sources]
        joined = "\n\n---\n\n".join(parts)
        if max_chars and len(joined) > max_chars:
            joined = joined[:max_chars] + "\n\n[... content truncated ...]"
        return joined

    def fingerprint(self) -> str:
        payload = json.dumps(
            {
                "type": self.artifact_type,
                "title": self.title,
                "sources": [{"t": s.title, "c": s.content[:200]} for s in self.sources],
                "config": self.config,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]


class ArtifactFile(BaseModel):
    path: str
    mime_type: str
    description: Optional[str] = None


class ArtifactResult(BaseModel):
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
    artifact_type: str = ""
    description: str = ""

    def __init__(self, llm: Optional[Any] = None) -> None:
        self._llm = llm

    @property
    def llm(self):
        if self._llm is None:
            from open_notebook.artifacts.llm import ArtifactLLM
            self._llm = ArtifactLLM.current()
        return self._llm

    def output_dir(self, request: ArtifactRequest) -> Path:
        base = Path(request.output_dir or ".artifact_output")
        base.mkdir(parents=True, exist_ok=True)
        return base

    def output_path(self, request: ArtifactRequest, extension: str, suffix: str = "") -> Path:
        fingerprint = request.fingerprint()
        stem = (request.title or self.artifact_type).lower()
        stem = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in stem)
        name = f"{stem}_{fingerprint}"
        if suffix:
            name += f"_{suffix}"
        return self.output_dir(request) / f"{name}.{extension.lstrip('.')}"

    @abc.abstractmethod
    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        ...
