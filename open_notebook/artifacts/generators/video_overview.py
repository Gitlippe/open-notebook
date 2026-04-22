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

        # TODO (Phase 2 Stream G): add video_renderer.py that reads beats.json and:
        #   1. Calls image_gen.py per beat (visual_prompt → PIL image)
        #   2. Calls TTS provider per beat (narration_script → audio file)
        #   3. Stitches via ffmpeg → MP4 at output_path(request, "mp4")
        #   4. Appends ArtifactFile(path=..., mime_type="video/mp4") to result.files

        total_words = sum(
            len(b.narration_script.split()) for b in result.beats
        )

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=result.title,
            summary=(
                f"{len(result.beats)}-beat video spec, "
                f"~{result.total_duration_seconds}s, "
                f"~{total_words} narration words"
            ),
            structured=data,
            files=[
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
            ],
            provenance=self.llm.provenance,
            metadata={
                "beat_count": len(result.beats),
                "total_duration_seconds": result.total_duration_seconds,
                "voice_provider": result.voice.provider,
                "voice_id": result.voice.voice_id,
                "total_narration_words": total_words,
                "phase2_renderer": "TODO: Stream G",
            },
        )
