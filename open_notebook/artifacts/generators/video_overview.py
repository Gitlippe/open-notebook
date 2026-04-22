"""Video Overview generator.

Produces a narrated video SPEC: title, total duration, voice metadata,
and a list of beats where each beat carries a narration script, a visual
prompt for image generation, and alt text.

Phase 1 deliverable: beats.json + Markdown script preview.
The video renderer (Phase 2 Stream G) consumes beats.json to perform:
  - TTS synthesis per beat (OpenAI tts-1-hd or ElevenLabs)
  - Image generation per beat (gpt-image-1 / imagen-3 via image_gen.py)
  - ffmpeg stitching → MP4

Coordination notes for Stream G:
  - beats.json root keys: title, total_duration_seconds, voice, beats[]
  - Each beat: {beat_index, duration_seconds, narration_script, visual_prompt, alt_text}
  - voice keys: provider (openai|elevenlabs), voice_id, speaking_rate
  - Stream G should look for the file at ArtifactFile with mime_type application/json + description containing "beats"
"""
from __future__ import annotations

import json
import os
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.llm import combine_prompts
from open_notebook.artifacts.prompts import (
    VIDEO_OVERVIEW_MAP_PROMPT,
    VIDEO_OVERVIEW_REDUCE_PROMPT,
)
from open_notebook.artifacts.registry import register_generator


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class BeatSchema(BaseModel):
    beat_index: int = Field(..., description="1-based beat index for ordering")
    duration_seconds: int = Field(
        ...,
        ge=5,
        le=120,
        description="Target narration duration for this beat in seconds (5-120s)",
    )
    narration_script: str = Field(
        ...,
        description=(
            "Full, verbatim narration script for this beat. "
            "Should be conversational and read naturally aloud."
        ),
    )
    visual_prompt: str = Field(
        ...,
        description=(
            "Image generation prompt for the background visual shown during this beat. "
            "Be specific: describe composition, style, colors, and key elements."
        ),
    )
    alt_text: str = Field(
        ...,
        description="Accessibility alt text for the beat's visual (1 sentence)",
    )


class VoiceMetadataSchema(BaseModel):
    provider: Literal["openai", "elevenlabs"] = Field(
        default="openai",
        description="TTS provider to use in Phase 2 rendering",
    )
    voice_id: str = Field(
        default="alloy",
        description="Provider-specific voice identifier (e.g. 'alloy', 'nova', 'onyx' for OpenAI)",
    )
    speaking_rate: float = Field(
        default=1.0,
        ge=0.5,
        le=2.0,
        description="Speaking rate multiplier (1.0 = normal speed)",
    )


class VideoOverviewSchema(BaseModel):
    title: str = Field(..., description="Video title — clear and engaging")
    total_duration_seconds: int = Field(
        ...,
        ge=30,
        description="Estimated total video duration in seconds (sum of beat durations)",
    )
    voice: VoiceMetadataSchema = Field(
        default_factory=VoiceMetadataSchema,
        description="TTS voice metadata for Phase 2 rendering",
    )
    beats: List[BeatSchema] = Field(
        ...,
        description=(
            "Ordered list of video beats (4-10 beats typical). "
            "Each beat is a self-contained scene with narration + visuals."
        ),
    )


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _render_markdown_script(schema: VideoOverviewSchema) -> str:
    """Render a human-readable Markdown script preview of the video."""
    lines = [
        f"# {schema.title}",
        "",
        f"**Total duration:** ~{schema.total_duration_seconds}s  ",
        f"**Voice:** {schema.voice.provider} / {schema.voice.voice_id} (rate: {schema.voice.speaking_rate}x)",
        "",
        "---",
        "",
    ]
    for beat in schema.beats:
        lines.append(f"## Beat {beat.beat_index} ({beat.duration_seconds}s)")
        lines.append("")
        lines.append(f"**Visual prompt:** {beat.visual_prompt}")
        lines.append(f"*Alt text: {beat.alt_text}*")
        lines.append("")
        lines.append(f"**Narration:**")
        lines.append("")
        lines.append(f"> {beat.narration_script}")
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

@register_generator
class VideoOverviewGenerator(BaseArtifactGenerator):
    artifact_type = "video_overview"
    description = (
        "Multi-beat narrated video spec (JSON + Markdown script). "
        "Phase 2 Stream G adds TTS + image gen + ffmpeg MP4 assembly."
    )
    default_model_type = "chat"

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        style = request.config.get("style", "documentary")
        target_duration = request.config.get("target_duration_seconds", 120)
        voice_id = request.config.get("voice_id", "alloy")
        voice_provider = request.config.get("voice_provider", "openai")

        def map_prompt(chunk: str) -> str:
            directive = VIDEO_OVERVIEW_MAP_PROMPT + (
                f"\nStyle: {style}. Target total duration: ~{target_duration}s. "
                f"Voice: {voice_provider}/{voice_id}."
            )
            return combine_prompts(directive, chunk)

        def reduce_prompt(partials: list[VideoOverviewSchema]) -> str:
            combined_json = json.dumps(
                [p.model_dump() for p in partials], indent=2
            )
            return combine_prompts(
                VIDEO_OVERVIEW_REDUCE_PROMPT + (
                    f"\nStyle: {style}. Target total duration: ~{target_duration}s. "
                    f"Voice: {voice_provider}/{voice_id}."
                ),
                combined_json,
            )

        result: VideoOverviewSchema = await self.chunked_generate(
            request,
            schema=VideoOverviewSchema,
            map_prompt_builder=map_prompt,
            reduce_prompt_builder=reduce_prompt,
        )

        # Override voice metadata from config if provided
        if voice_id != "alloy" or voice_provider != "openai":
            result = result.model_copy(
                update={
                    "voice": VoiceMetadataSchema(
                        provider=voice_provider,
                        voice_id=voice_id,
                        speaking_rate=request.config.get("speaking_rate", 1.0),
                    )
                }
            )

        data = result.model_dump()

        # beats.json — primary output consumed by Phase 2 Stream G
        json_path = self.output_path(request, "json")
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        # Markdown script preview — human-readable
        md_path = self.output_path(request, "md")
        md_path.write_text(_render_markdown_script(result), encoding="utf-8")

        total_words = sum(
            len(b.narration_script.split()) for b in result.beats
        )

        artifact_files = [
            ArtifactFile(
                path=str(json_path),
                mime_type="application/json",
                description="beats.json — video spec for Phase 2 Stream G renderer",
            ),
            ArtifactFile(
                path=str(md_path),
                mime_type="text/markdown",
                description="Narration script preview (Markdown)",
            ),
        ]
        mp4_rendered = False

        # Phase 2 Stream G wiring: call the video renderer when requested.
        # Set ARTIFACT_RENDER_VIDEO=1 to trigger full render (TTS + image gen + ffmpeg).
        # Requires Stream D (image_gen.py) to be merged first.
        if os.environ.get("ARTIFACT_RENDER_VIDEO", "").strip() == "1":
            from open_notebook.artifacts.renderers.video_renderer import render_video
            mp4_path = self.output_path(request, "mp4")
            try:
                await render_video(result, mp4_path)
                artifact_files.append(
                    ArtifactFile(
                        path=str(mp4_path),
                        mime_type="video/mp4",
                        description="Rendered video (MP4 H.264 + AAC, 1080p 30fps)",
                    )
                )
                mp4_rendered = True
            except Exception as render_err:
                # Log but do not fail the artifact generation; the spec files are still valid.
                import logging as _logging
                _logging.getLogger(__name__).warning(
                    f"Stream G render_video failed (beats.json still written): {render_err}"
                )

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=result.title,
            summary=(
                f"{len(result.beats)}-beat video spec, "
                f"~{result.total_duration_seconds}s, "
                f"~{total_words} narration words"
                + (" (MP4 rendered)" if mp4_rendered else "")
            ),
            structured=data,
            files=artifact_files,
            provenance=self.llm.provenance,
            metadata={
                "beat_count": len(result.beats),
                "total_duration_seconds": result.total_duration_seconds,
                "voice_provider": result.voice.provider,
                "voice_id": result.voice.voice_id,
                "total_narration_words": total_words,
                "mp4_rendered": mp4_rendered,
            },
        )
