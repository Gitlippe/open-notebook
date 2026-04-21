"""Service layer for artifact generation.

Orchestrates calls into ``open_notebook.artifacts`` for the FastAPI router.
Optionally pulls content from a notebook's sources and notes when a
``notebook_id`` is supplied.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from loguru import logger

from open_notebook.artifacts import (
    generate_artifact,
    list_artifact_types,
)
from open_notebook.artifacts.base import ArtifactRequest, ArtifactResult, ArtifactSource
from open_notebook.artifacts.registry import get_generator
from open_notebook.config import DATA_FOLDER


async def _sources_from_notebook(notebook_id: str) -> List[ArtifactSource]:
    """Build ``ArtifactSource`` objects from a Notebook's records.

    Falls back to an empty list on any failure so callers can still
    operate on explicit ``sources`` payloads without a DB.
    """
    try:
        from open_notebook.domain.notebook import Notebook
    except Exception as exc:  # pragma: no cover - domain layer missing
        logger.warning(f"Notebook domain unavailable: {exc}")
        return []

    try:
        nb = await Notebook.get(notebook_id)
    except Exception as exc:
        logger.warning(f"Failed to load notebook {notebook_id}: {exc}")
        return []

    sources: List[ArtifactSource] = []
    try:
        db_sources = await nb.get_sources()
    except Exception:
        db_sources = []
    for s in db_sources or []:
        content = getattr(s, "full_text", None) or getattr(s, "content", "") or ""
        if not content:
            continue
        sources.append(
            ArtifactSource(
                title=getattr(s, "title", None) or getattr(s, "topic", "Source"),
                content=content,
                url=getattr(s, "url", None),
                metadata={"source_id": str(getattr(s, "id", ""))},
            )
        )
    try:
        notes = await nb.get_notes()
    except Exception:
        notes = []
    for n in notes or []:
        content = getattr(n, "content", "") or ""
        if not content:
            continue
        sources.append(
            ArtifactSource(
                title=getattr(n, "title", None) or "Note",
                content=content,
                metadata={"note_id": str(getattr(n, "id", ""))},
            )
        )
    return sources


def _artifact_output_dir() -> str:
    base = os.path.join(DATA_FOLDER or ".", "artifacts")
    os.makedirs(base, exist_ok=True)
    return base


async def generate(
    artifact_type: str,
    sources: Optional[List[Dict[str, Any]]] = None,
    notebook_id: Optional[str] = None,
    title: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    model_id: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> ArtifactResult:
    """Synchronous (in-process) artifact generation."""
    src_models: List[ArtifactSource] = []
    if sources:
        for s in sources:
            if isinstance(s, ArtifactSource):
                src_models.append(s)
            else:
                src_models.append(ArtifactSource(**s))
    if notebook_id:
        src_models.extend(await _sources_from_notebook(notebook_id))
    if not src_models:
        raise ValueError(
            "No sources provided. Pass 'sources' directly or supply a notebook_id."
        )

    return await generate_artifact(
        artifact_type=artifact_type,
        sources=src_models,
        title=title,
        config=config,
        model_id=model_id,
        output_dir=output_dir or _artifact_output_dir(),
    )


def available_types() -> List[Dict[str, str]]:
    return list_artifact_types()
