"""HTTP endpoints for artifact generation.

Mirrors the podcast async pattern:
- POST /artifacts/generate submits a surreal-commands job and returns {job_id}.
- GET /artifacts/jobs/{job_id} polls status.
- GET /artifacts/download streams a generated file (path-traversal guarded).
- GET /artifacts/types lists every registered generator.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from api import artifact_service
from open_notebook.config import ARTIFACT_OUTPUT_ROOT

router = APIRouter()


class ArtifactSourceIn(BaseModel):
    title: str = Field(..., description="Source title or identifier")
    content: str = Field(..., description="Raw text content")
    url: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ArtifactGenerateRequest(BaseModel):
    artifact_type: str = Field(..., description="e.g. 'briefing', 'slide_deck'")
    sources: List[ArtifactSourceIn] = Field(default_factory=list)
    notebook_id: Optional[str] = None
    title: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    model_id: Optional[str] = None
    output_dir: Optional[str] = None


class ArtifactJobSubmitted(BaseModel):
    job_id: str
    status: str = "submitted"


class ArtifactFileOut(BaseModel):
    path: str
    mime_type: str
    description: Optional[str] = None


class ArtifactJobResult(BaseModel):
    """Shape returned by GET /artifacts/jobs/{id} when complete."""

    status: str
    artifact_type: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    structured: Dict[str, Any] = Field(default_factory=dict)
    files: List[ArtifactFileOut] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    provenance: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    generated_at: Optional[str] = None


@router.get("/artifacts/types")
async def list_types() -> Dict[str, Any]:
    """Return the registered artifact types and their descriptions."""
    return {"types": artifact_service.available_types()}


@router.post("/artifacts/generate", response_model=ArtifactJobSubmitted)
async def generate(request: ArtifactGenerateRequest) -> ArtifactJobSubmitted:
    """Submit an artifact-generation job to the surreal-commands queue.

    The job runs asynchronously; poll GET /artifacts/jobs/{job_id}.
    """
    job_id = await artifact_service.submit_generation_job(
        artifact_type=request.artifact_type,
        sources=[s.model_dump() for s in request.sources],
        notebook_id=request.notebook_id,
        title=request.title,
        config=request.config,
        model_id=request.model_id,
        output_dir=request.output_dir,
    )
    return ArtifactJobSubmitted(job_id=job_id, status="submitted")


@router.get("/artifacts/jobs/{job_id}", response_model=ArtifactJobResult)
async def get_job(job_id: str) -> ArtifactJobResult:
    """Return the current status + payload of an artifact generation job."""
    return await artifact_service.get_job_status(job_id)


@router.get("/artifacts/download")
async def download(path: str) -> FileResponse:
    """Return a generated artifact file.

    Path-traversal guarded: the resolved path must sit inside
    ``ARTIFACT_OUTPUT_ROOT`` (see ``open_notebook/config.py``).
    """
    root = Path(ARTIFACT_OUTPUT_ROOT).resolve()
    try:
        p = Path(path).resolve(strict=True)
    except (FileNotFoundError, RuntimeError):
        raise HTTPException(status_code=404, detail="File not found")

    if not p.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    try:
        p.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=403, detail="Path is outside artifact root")

    return FileResponse(str(p), filename=p.name)
