"""Service layer for artifact generation.

Mirrors the podcast async pattern:
1. ``submit_generation_job`` pushes a job onto surreal-commands and returns
   an opaque ``job_id`` string.
2. ``get_job_status`` polls the queue for progress / result / error.
3. The in-process ``generate`` helper is preserved so the command implementation
   (and unit tests) can call it directly.

The HTTP router never calls ``generate`` directly — it must go through
``submit_generation_job`` so long-running LLM + rendering work does not tie
up an HTTP worker.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from loguru import logger
from surreal_commands import get_command_status, submit_command

from open_notebook.artifacts import (
    generate_artifact,
    list_artifact_types,
)
from open_notebook.artifacts.base import ArtifactRequest, ArtifactResult, ArtifactSource
from open_notebook.config import ARTIFACT_OUTPUT_ROOT


# ---------------------------------------------------------------------------
# Notebook hydration (pull sources + notes to feed the generator)
# ---------------------------------------------------------------------------

async def _sources_from_notebook(notebook_id: str) -> List[ArtifactSource]:
    """Build ``ArtifactSource`` objects from a Notebook's records.

    Returns an empty list on any DB failure so callers can still operate on
    explicit ``sources`` payloads even when SurrealDB is down.
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


# ---------------------------------------------------------------------------
# Public API (router surface)
# ---------------------------------------------------------------------------

def available_types() -> List[Dict[str, str]]:
    """Return the registered artifact-type catalogue."""
    return list_artifact_types()


async def submit_generation_job(
    artifact_type: str,
    sources: Optional[List[Dict[str, Any]]] = None,
    notebook_id: Optional[str] = None,
    title: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    model_id: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> str:
    """Submit an artifact-generation job to the surreal-commands queue.

    Returns the opaque ``job_id`` string. The job runs asynchronously.
    """
    # Import the command module so surreal_commands can resolve the @command
    # decorator's registry entry. Mirrors the podcast_service pattern.
    try:
        import commands.artifact_commands  # noqa: F401
    except ImportError as exc:  # pragma: no cover
        logger.error(f"Failed to import artifact commands: {exc}")
        raise HTTPException(
            status_code=500,
            detail="artifact commands module not available",
        )

    command_args: Dict[str, Any] = {
        "artifact_type": artifact_type,
        "sources": sources or [],
        "notebook_id": notebook_id,
        "title": title,
        "config": config or {},
        "model_id": model_id,
        "output_dir": output_dir or ARTIFACT_OUTPUT_ROOT,
    }

    try:
        job_id = submit_command("open_notebook", "generate_artifact", command_args)
    except Exception as exc:
        logger.error(f"submit_command failed for artifact_type={artifact_type}: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit artifact generation job: {exc}",
        )

    if not job_id:
        raise HTTPException(
            status_code=500, detail="submit_command returned no job_id"
        )

    job_id_str = str(job_id)
    logger.info(
        f"Submitted artifact generation job {job_id_str} "
        f"(artifact_type={artifact_type}, title={title})"
    )
    return job_id_str


async def get_job_status(job_id: str) -> Dict[str, Any]:
    """Return the current status of an artifact-generation job."""
    try:
        status = await get_command_status(job_id)
    except Exception as exc:
        logger.error(f"Failed to get artifact job status: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get job status: {exc}"
        )

    if status is None:
        return {"status": "unknown", "job_id": job_id}

    result = getattr(status, "result", None) or {}
    return {
        "status": status.status,
        "job_id": job_id,
        "artifact_type": result.get("artifact_type"),
        "title": result.get("title"),
        "summary": result.get("summary"),
        "structured": result.get("structured") or {},
        "files": result.get("files") or [],
        "metadata": result.get("metadata") or {},
        "provenance": result.get("provenance"),
        "generated_at": result.get("generated_at"),
        "error": getattr(status, "error_message", None),
    }


# ---------------------------------------------------------------------------
# In-process entry point (used by the surreal-commands worker + unit tests)
# ---------------------------------------------------------------------------

async def generate(
    artifact_type: str,
    sources: Optional[List[Dict[str, Any]]] = None,
    notebook_id: Optional[str] = None,
    title: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    model_id: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> ArtifactResult:
    """In-process artifact generation.

    Called by the surreal-commands worker (see ``commands/artifact_commands.py``)
    and by unit tests. The HTTP router must NOT call this directly — it must
    go through ``submit_generation_job``.
    """
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
        output_dir=output_dir or ARTIFACT_OUTPUT_ROOT,
    )
