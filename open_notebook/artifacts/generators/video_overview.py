"""Video Overview generator — STUB (Phase 1 Stream C).

This module is intentionally a scaffolding placeholder until Stream C lands
the real implementation. It registers the artifact type so the router and
registry are complete; any attempt to actually generate raises
``NotImplementedError`` so no fake output ever ships.
"""
from __future__ import annotations

from open_notebook.artifacts.base import (
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.registry import register_generator


@register_generator
class VideoOverviewGenerator(BaseArtifactGenerator):
    artifact_type = "video_overview"
    description = (
        "Multi-beat narrated video with per-beat visuals (TTS + image gen + ffmpeg)."
    )
    default_model_type = "chat"

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        raise NotImplementedError(
            "VideoOverviewGenerator is pending Phase 1 Stream C delivery."
        )
