"""Background command for async artifact generation.

Registers ``generate_artifact`` with surreal-commands so long-running
artifact jobs run on the queue rather than tying up an HTTP worker.

Retries: 5 attempts, exponential jitter 1-60s, stop_on ``ValueError`` so
validation failures don't retry.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from loguru import logger
from surreal_commands import CommandInput, CommandOutput, command

from api import artifact_service


class ArtifactGenerationInput(CommandInput):
    artifact_type: str
    sources: List[Dict[str, Any]] = []
    notebook_id: Optional[str] = None
    title: Optional[str] = None
    config: Dict[str, Any] = {}
    model_id: Optional[str] = None
    output_dir: Optional[str] = None


class ArtifactGenerationOutput(CommandOutput):
    success: bool
    artifact_type: str
    title: Optional[str] = None
    summary: Optional[str] = None
    files: List[Dict[str, str]] = []
    structured: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}
    provenance: Optional[Dict[str, Any]] = None
    generated_at: Optional[str] = None
    processing_time: float = 0.0
    error_message: Optional[str] = None


@command(
    "generate_artifact",
    app="open_notebook",
    retry={
        "max_attempts": 5,
        "wait_strategy": "exponential_jitter",
        "stop_on": [ValueError],
    },
)
async def generate_artifact_command(
    input_data: ArtifactGenerationInput,
) -> ArtifactGenerationOutput:
    start = time.time()
    try:
        logger.info(
            f"Starting artifact generation: type={input_data.artifact_type} "
            f"title={input_data.title}"
        )
        result = await artifact_service.generate(
            artifact_type=input_data.artifact_type,
            sources=input_data.sources,
            notebook_id=input_data.notebook_id,
            title=input_data.title,
            config=input_data.config,
            model_id=input_data.model_id,
            output_dir=input_data.output_dir,
        )
        return ArtifactGenerationOutput(
            success=True,
            artifact_type=result.artifact_type,
            title=result.title,
            summary=result.summary,
            structured=result.structured,
            files=[
                {
                    "path": f.path,
                    "mime_type": f.mime_type,
                    "description": f.description or "",
                }
                for f in result.files
            ],
            metadata=result.metadata,
            provenance=result.provenance.model_dump()
            if result.provenance is not None
            else None,
            generated_at=result.generated_at,
            processing_time=time.time() - start,
        )
    except ValueError as exc:
        # Validation failure — don't retry.
        logger.warning(f"Artifact generation validation failure: {exc}")
        return ArtifactGenerationOutput(
            success=False,
            artifact_type=input_data.artifact_type,
            error_message=str(exc),
            processing_time=time.time() - start,
        )
    except Exception as exc:
        # Transient or provider error — let surreal-commands retry.
        logger.exception(f"Artifact generation failed: {exc}")
        raise
