"""Video renderer for Open Notebook artifact pipeline.

Phase 2 Stream G: takes a ``VideoOverviewSchema`` (beats.json) produced by the
Phase 1 generator and turns it into an MP4 via three sub-pipelines:

1. **Image generation** — one image per beat, sourced from Stream D's
   ``open_notebook.artifacts.image_gen.generate_image``.  If that module is
   not available yet (Stream D still in-flight), import fails loudly rather
   than silently substituting fake images.  Gate all image calls behind a
   try/except ImportError so that the unit-test suite can still import *this*
   module, but surface the error at render-time.

2. **TTS per beat** — routes to OpenAI ``tts-1-hd`` or ElevenLabs depending on
   ``schema.voice.provider``.  Beats are synthesised concurrently via
   ``asyncio.gather``.

3. **ffmpeg stitching** — per-beat silent video clip (image + Ken Burns pan)
   with audio overlay; beats concatenated via the concat demuxer; final output
   is MP4 H.264 + AAC, 1080p 30fps.

Public API
----------
``async def render_video(schema, output_path) -> Path``
    Full render.  Raises ``ExternalServiceError`` on failure.

``async def render_video_stub(schema, output_path) -> Path``
    1-second silent MP4 with the script baked into Matroska metadata.
    Only available when ``ARTIFACT_RENDER_STUB=1``.
    Raises ``RuntimeError`` when ``ENV=production``.

Stream D dependency
-------------------
``image_gen.py`` is owned by Stream D and may not exist on this branch yet.
If it is absent, ``render_video`` raises ``ExternalServiceError`` with a
message explaining the dependency.  The stub path does **not** call
``image_gen`` and is safe to run without Stream D.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Optional

import ffmpeg
from loguru import logger

from open_notebook.exceptions import ExternalServiceError

# ---------------------------------------------------------------------------
# Import VideoOverviewSchema from the generator (same module, no circularity)
# ---------------------------------------------------------------------------
from open_notebook.artifacts.generators.video_overview import (  # noqa: E402
    VideoOverviewSchema,
    BeatSchema,
)

# ---------------------------------------------------------------------------
# Env-var guards
# ---------------------------------------------------------------------------

_STUB_ENV = "ARTIFACT_RENDER_STUB"
_ENV_VAR = "ENV"
_RENDER_VIDEO_ENV = "ARTIFACT_RENDER_VIDEO"

# Resolution + framerate constants
_WIDTH = 1920
_HEIGHT = 1080
_FPS = 30

# ---------------------------------------------------------------------------
# image_gen lazy import — Stream D dependency
# ---------------------------------------------------------------------------
_IMAGE_GEN_AVAILABLE: Optional[bool] = None


def _require_image_gen():
    """Return the generate_image callable or raise ExternalServiceError."""
    global _IMAGE_GEN_AVAILABLE
    try:
        from open_notebook.artifacts.image_gen import generate_image  # type: ignore
        _IMAGE_GEN_AVAILABLE = True
        return generate_image
    except ImportError as exc:
        _IMAGE_GEN_AVAILABLE = False
        raise ExternalServiceError(
            "Stream G depends on Stream D's open_notebook.artifacts.image_gen module "
            "which has not been committed to this branch yet.  "
            "Merge Stream D (feat/artifacts-D-pptx) before running render_video()."
        ) from exc


# ---------------------------------------------------------------------------
# TTS helpers
# ---------------------------------------------------------------------------

async def _tts_openai(narration: str, voice_id: str, speaking_rate: float) -> bytes:
    """Call OpenAI TTS and return MP3 bytes."""
    import openai  # pulled from project deps

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ExternalServiceError("OPENAI_API_KEY not set; cannot call OpenAI TTS.")

    try:
        client = openai.AsyncOpenAI(api_key=api_key)
        response = await client.audio.speech.create(
            model="tts-1-hd",
            voice=voice_id,  # type: ignore[arg-type]
            input=narration,
            speed=speaking_rate,
        )
        # response.content for newer SDK; response.read() for older
        if hasattr(response, "content"):
            return response.content
        return await response.aread()
    except Exception as exc:
        raise ExternalServiceError(f"OpenAI TTS failed: {exc}") from exc


async def _tts_elevenlabs(narration: str, voice_id: str, speaking_rate: float) -> bytes:
    """Call ElevenLabs TTS and return MP3 bytes."""
    from elevenlabs import AsyncElevenLabs  # type: ignore

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise ExternalServiceError("ELEVENLABS_API_KEY not set; cannot call ElevenLabs TTS.")

    try:
        client = AsyncElevenLabs(api_key=api_key)
        audio = b""
        async for chunk in await client.text_to_speech.convert(
            voice_id=voice_id,
            text=narration,
            voice_settings={"speed": speaking_rate} if speaking_rate != 1.0 else None,
            model_id="eleven_turbo_v2_5",
            output_format="mp3_44100_128",
        ):
            audio += chunk
        return audio
    except Exception as exc:
        raise ExternalServiceError(f"ElevenLabs TTS failed: {exc}") from exc


async def _synthesize_beat(beat: BeatSchema, voice_provider: str, voice_id: str, speaking_rate: float) -> bytes:
    """Route to the correct TTS provider and return audio bytes."""
    if voice_provider == "openai":
        return await _tts_openai(beat.narration_script, voice_id, speaking_rate)
    elif voice_provider == "elevenlabs":
        return await _tts_elevenlabs(beat.narration_script, voice_id, speaking_rate)
    else:
        raise ExternalServiceError(
            f"Unknown TTS provider '{voice_provider}'. Supported: openai, elevenlabs."
        )


# ---------------------------------------------------------------------------
# ffmpeg clip builder
# ---------------------------------------------------------------------------

def _build_beat_clip(
    image_path: str,
    audio_path: str,
    duration: float,
    output_path: str,
) -> None:
    """
    Build a single beat's video clip:
    - Ken Burns zoom-in pan from 105% → 100% of the image
    - Audio overlay
    - H.264 + AAC, 1920x1080, 30fps

    Raises ExternalServiceError if ffmpeg fails.
    """
    try:
        # Video input: image looped for `duration` seconds with Ken Burns effect
        video_in = ffmpeg.input(
            image_path,
            loop=1,
            t=duration,
            framerate=_FPS,
        )

        # Ken Burns: scale up 5% then slowly zoom back to 100%
        # vf filter string: zoompan with mild pan + zoom
        zoom_pan = (
            f"scale={_WIDTH * 2}:{_HEIGHT * 2},"  # oversample for zoom headroom
            f"zoompan=z='if(lte(zoom,1.0),1.05,max(1.0,zoom-0.0015))':"
            f"x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':"
            f"d={int(duration * _FPS)}:s={_WIDTH}x{_HEIGHT}:fps={_FPS}"
        )

        video = video_in.video.filter("zoompan",
                                      z=f"if(lte(zoom,1.0),1.05,max(1.0,zoom-0.0015))",
                                      x="iw/2-(iw/zoom/2)",
                                      y="ih/2-(ih/zoom/2)",
                                      d=int(duration * _FPS),
                                      s=f"{_WIDTH}x{_HEIGHT}",
                                      fps=_FPS)

        # Audio input
        audio_in = ffmpeg.input(audio_path)

        # Output: encode to H.264 + AAC, trim to duration
        (
            ffmpeg
            .output(
                video,
                audio_in.audio,
                output_path,
                vcodec="libx264",
                acodec="aac",
                pix_fmt="yuv420p",
                t=duration,
                shortest=None,
                **{"b:a": "128k"},
            )
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        raise ExternalServiceError(f"ffmpeg clip build failed: {stderr}") from exc


def _concat_clips(clip_paths: list[str], output_path: str) -> None:
    """Concatenate beat clips using ffmpeg concat demuxer."""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as f:
            concat_list = f.name
            for p in clip_paths:
                f.write(f"file '{p}'\n")

        (
            ffmpeg
            .input(concat_list, format="concat", safe=0)
            .output(output_path, vcodec="copy", acodec="copy")
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        raise ExternalServiceError(f"ffmpeg concat failed: {stderr}") from exc
    finally:
        try:
            os.unlink(concat_list)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Public render functions
# ---------------------------------------------------------------------------

async def render_video(schema: VideoOverviewSchema, output_path: Path) -> Path:
    """Render a ``VideoOverviewSchema`` to an MP4 file.

    Pipeline:
    1. Parallelise TTS synthesis across all beats.
    2. Parallelise image generation across all beats (requires Stream D).
    3. For each beat: build a single clip (image + Ken Burns + audio).
    4. Concatenate all beat clips.

    Returns ``output_path`` on success.
    Raises ``ExternalServiceError`` on any failure (TTS, image gen, ffmpeg).

    Stream D dependency: if ``open_notebook.artifacts.image_gen`` is not
    available, raises ``ExternalServiceError`` with an explanatory message.
    """
    generate_image = _require_image_gen()  # raises if Stream D not landed

    voice = schema.voice
    logger.info(
        f"render_video: {len(schema.beats)} beats, provider={voice.provider}, "
        f"voice_id={voice.voice_id}, output={output_path}"
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="onb_video_") as tmp_dir:
        tmp = Path(tmp_dir)

        # 1. TTS synthesis (all beats in parallel)
        logger.info("render_video: synthesising TTS for all beats…")
        tts_tasks = [
            _synthesize_beat(beat, voice.provider, voice.voice_id, voice.speaking_rate)
            for beat in schema.beats
        ]
        audio_bytes_list: list[bytes] = await asyncio.gather(*tts_tasks)

        # Write audio bytes to temp files
        audio_paths: list[str] = []
        for i, audio_bytes in enumerate(audio_bytes_list):
            ap = str(tmp / f"beat_{i:03d}_audio.mp3")
            Path(ap).write_bytes(audio_bytes)
            audio_paths.append(ap)

        # 2. Image generation (all beats in parallel)
        logger.info("render_video: generating images for all beats…")
        image_tasks = [
            asyncio.to_thread(generate_image, beat.visual_prompt, size="1920x1080")
            for beat in schema.beats
        ]
        image_bytes_list: list[bytes] = await asyncio.gather(*image_tasks)

        # Write image bytes to temp PNG files
        image_paths: list[str] = []
        for i, image_bytes in enumerate(image_bytes_list):
            ip = str(tmp / f"beat_{i:03d}_image.png")
            Path(ip).write_bytes(image_bytes)
            image_paths.append(ip)

        # 3. Build per-beat clips
        logger.info("render_video: building per-beat clips…")
        clip_paths: list[str] = []
        for i, beat in enumerate(schema.beats):
            clip_path = str(tmp / f"beat_{i:03d}_clip.mp4")
            _build_beat_clip(
                image_path=image_paths[i],
                audio_path=audio_paths[i],
                duration=float(beat.duration_seconds),
                output_path=clip_path,
            )
            clip_paths.append(clip_path)

        # 4. Concatenate all clips
        if len(clip_paths) == 1:
            # Only one beat: just copy the single clip to output
            import shutil
            shutil.copy2(clip_paths[0], str(output_path))
        else:
            logger.info("render_video: concatenating clips…")
            _concat_clips(clip_paths, str(output_path))

    logger.info(f"render_video: complete → {output_path}")
    return output_path


async def render_video_stub(schema: VideoOverviewSchema, output_path: Path) -> Path:
    """Write a 1-second silent MP4 with the narration script in metadata.

    Only enabled when ``ARTIFACT_RENDER_STUB=1``.
    Raises ``RuntimeError`` when ``ENV=production`` to prevent accidental
    stub leakage into production deployments.

    Intended for fast local dev loops where real TTS + image gen would be
    slow and expensive.
    """
    if os.environ.get(_ENV_VAR, "").lower() == "production":
        raise RuntimeError(
            "render_video_stub() is disabled in production (ENV=production). "
            "Unset ARTIFACT_RENDER_STUB or run outside production."
        )
    if os.environ.get(_STUB_ENV, "").strip() != "1":
        raise RuntimeError(
            "render_video_stub() called without ARTIFACT_RENDER_STUB=1. "
            "Set the env var to enable stub rendering."
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Collect the full narration text to embed in metadata
    full_script = "\n\n".join(
        f"[Beat {b.beat_index}] {b.narration_script}" for b in schema.beats
    )
    # Escape single quotes for ffmpeg metadata value
    metadata_script = full_script.replace("\\", "\\\\").replace("'", "\\'").replace("=", "\\=").replace(";", "\\;").replace("#", "\\#").replace("\n", " | ")

    logger.info(f"render_video_stub: writing 1s silent MP4 stub → {output_path}")

    try:
        (
            ffmpeg
            .input("anullsrc=r=44100:cl=mono", format="lavfi", t=1)
            .output(
                str(output_path),
                vcodec="libx264",
                acodec="aac",
                pix_fmt="yuv420p",
                s=f"{_WIDTH}x{_HEIGHT}",
                r=_FPS,
                t=1,
                **{
                    "metadata": f"comment={metadata_script}",
                    "metadata:g:0": f"title={schema.title}",
                },
            )
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as exc:
        # ffmpeg-python's anullsrc without a video source can be awkward;
        # fall back to lavfi color source + anullsrc
        try:
            video_in = ffmpeg.input(
                "color=size=1920x1080:rate=30:color=black", format="lavfi", t=1
            )
            audio_in = ffmpeg.input("anullsrc=r=44100:cl=mono", format="lavfi", t=1)
            (
                ffmpeg
                .output(
                    video_in,
                    audio_in,
                    str(output_path),
                    vcodec="libx264",
                    acodec="aac",
                    pix_fmt="yuv420p",
                    t=1,
                    **{
                        "metadata:g:0": f"title={schema.title}",
                        "metadata:g:1": f"comment={metadata_script}",
                    },
                )
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
        except ffmpeg.Error as exc2:
            stderr = exc2.stderr.decode("utf-8", errors="replace") if exc2.stderr else ""
            raise ExternalServiceError(f"ffmpeg stub render failed: {stderr}") from exc2

    logger.info(f"render_video_stub: done → {output_path}")
    return output_path
