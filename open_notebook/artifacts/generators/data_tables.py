"""Data Tables generator — STUB (Phase 1 Stream C).

Placeholder so the registry is complete. Any real call raises
``NotImplementedError`` — no fake output.
"""
from __future__ import annotations

from open_notebook.artifacts.base import (
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.registry import register_generator


@register_generator
class DataTablesGenerator(BaseArtifactGenerator):
    artifact_type = "data_tables"
    description = (
        "Structured tabular extraction rendered as CSV/XLSX/HTML."
    )
    default_model_type = "transformation"

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        raise NotImplementedError(
            "DataTablesGenerator is pending Phase 1 Stream C delivery."
        )
