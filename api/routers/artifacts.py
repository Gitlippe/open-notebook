"""HTTP endpoints for artifact generation.

Exposes the twelve built-in artifact generators and their metadata.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from api import artifact_service

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


class ArtifactFileOut(BaseModel):
    path: str
    mime_type: str
    description: Optional[str] = None


class ArtifactGenerateResponse(BaseModel):
    artifact_type: str
    title: str
    summary: Optional[str] = None
    structured: Dict[str, Any]
    files: List[ArtifactFileOut]
    metadata: Dict[str, Any]
    generated_at: str


@router.get("/artifacts/types")
async def list_types() -> Dict[str, Any]:
    return {"types": artifact_service.available_types()}


@router.post("/artifacts/generate", response_model=ArtifactGenerateResponse)
async def generate(request: ArtifactGenerateRequest) -> ArtifactGenerateResponse:
    try:
        result = await artifact_service.generate(
            artifact_type=request.artifact_type,
            sources=[s.model_dump() for s in request.sources],
            notebook_id=request.notebook_id,
            title=request.title,
            config=request.config,
            model_id=request.model_id,
            output_dir=request.output_dir,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return ArtifactGenerateResponse(
        artifact_type=result.artifact_type,
        title=result.title,
        summary=result.summary,
        structured=result.structured,
        files=[
            ArtifactFileOut(
                path=f.path, mime_type=f.mime_type, description=f.description
            )
            for f in result.files
        ],
        metadata=result.metadata,
        generated_at=result.generated_at,
    )


@router.get("/artifacts/download")
async def download(path: str):
    """Return an artifact file by absolute path.

    The path must point to a file that already exists on disk. This is
    intentionally simple because artifacts are generated locally; in a
    hardened deployment you would restrict this to a known artifacts root.
    """
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(p), filename=p.name)
