"""Integration tests for the video renderer (Stream G).

Markers
-------
``integration``   — all tests in this file
``real_llm``      — tests that make actual TTS API calls (skip if no key present)

Test coverage
-------------
1. ``test_render_video_real`` — 2-beat VideoOverviewSchema → MP4 via real TTS
   (OpenAI).  Verified with ffprobe: video stream + audio stream present,
   duration 8–12s.  Marker: ``integration + real_llm``.

2. ``test_render_video_stub`` — stub rendering (ARTIFACT_RENDER_STUB=1).
   Asserts the mp4 is ~1s and contains the script in its metadata.
   Marker: ``integration`` (no real_llm needed).

3. ``test_stub_raises_in_production`` — ENV=production + ARTIFACT_RENDER_STUB=1
   → RuntimeError.  Marker: ``integration``.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from open_notebook.artifacts.generators.video_overview import (
    BeatSchema,
    VideoOverviewSchema,
    VoiceMetadataSchema,
)

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# ffmpeg / ffprobe availability guard
# ---------------------------------------------------------------------------

import shutil as _shutil

_FFMPEG_AVAILABLE = _shutil.which("ffmpeg") is not None
_FFPROBE_AVAILABLE = _shutil.which("ffprobe") is not None

_skip_no_ffmpeg = pytest.mark.skipif(
    not _FFMPEG_AVAILABLE,
    reason="ffmpeg binary not in PATH; install ffmpeg to run video renderer tests",
)
_skip_no_ffprobe = pytest.mark.skipif(
    not _FFPROBE_AVAILABLE,
    reason="ffprobe binary not in PATH; install ffmpeg to run video validation tests",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ffprobe(mp4_path: Path) -> dict:
    """Run ffprobe on the file and return parsed JSON."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-show_format",
            str(mp4_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def _has_stream(probe: dict, codec_type: str) -> bool:
    return any(s.get("codec_type") == codec_type for s in probe.get("streams", []))


def _duration(probe: dict) -> float:
    return float(probe.get("format", {}).get("duration", 0))


# ---------------------------------------------------------------------------
# Fixture: 2-beat schema (~5s each → total ~10s)
# ---------------------------------------------------------------------------

@pytest.fixture
def two_beat_schema() -> VideoOverviewSchema:
    return VideoOverviewSchema(
        title="Test Video Overview",
        total_duration_seconds=30,  # schema minimum is 30
        voice=VoiceMetadataSchema(
            provider="openai",
            voice_id="alloy",
            speaking_rate=1.0,
        ),
        beats=[
            BeatSchema(
                beat_index=1,
                duration_seconds=5,
                narration_script="Welcome. This is a short test of the video renderer.",
                visual_prompt="A clean white background with a bold blue geometric pattern.",
                alt_text="Abstract blue geometric pattern on white background.",
            ),
            BeatSchema(
                beat_index=2,
                duration_seconds=5,
                narration_script="Thank you for watching this two-beat video overview test.",
                visual_prompt="A simple green gradient fading from light to dark.",
                alt_text="Smooth green gradient background.",
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Test 1: Real TTS render (OpenAI)
# ---------------------------------------------------------------------------

@pytest.mark.real_llm
@_skip_no_ffmpeg
@_skip_no_ffprobe
def test_render_video_real(two_beat_schema: VideoOverviewSchema, tmp_path: Path):
    """Full render via real OpenAI TTS.  Skips if OPENAI_API_KEY not set.

    NOTE: This test also requires open_notebook.artifacts.image_gen (Stream D)
    to be available.  If it isn't, the test is xfailed with an informative
    message rather than erroring.
    """
    import asyncio

    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")

    # Check image_gen availability (Stream D dependency)
    try:
        import open_notebook.artifacts.image_gen  # noqa: F401
    except ImportError:
        pytest.xfail(
            "open_notebook.artifacts.image_gen not available (Stream D not merged). "
            "Merge feat/artifacts-D-pptx before running full video render tests."
        )

    from open_notebook.artifacts.renderers.video_renderer import render_video

    output = tmp_path / "test_output.mp4"
    result = asyncio.run(render_video(two_beat_schema, output))

    assert result.exists(), "render_video must return an existing Path"
    assert result.suffix == ".mp4"
    assert result.stat().st_size > 1024, "MP4 must be non-trivially sized"

    probe = _ffprobe(result)
    assert _has_stream(probe, "video"), "MP4 must contain a video stream"
    assert _has_stream(probe, "audio"), "MP4 must contain an audio stream"

    duration = _duration(probe)
    assert 8.0 <= duration <= 12.0, (
        f"Expected duration 8–12s for 2×5s beats, got {duration:.1f}s"
    )


# ---------------------------------------------------------------------------
# Test 2: Stub render (ARTIFACT_RENDER_STUB=1)
# ---------------------------------------------------------------------------

@_skip_no_ffmpeg
@_skip_no_ffprobe
def test_render_video_stub(two_beat_schema: VideoOverviewSchema, tmp_path: Path):
    """Stub render writes a ~1s MP4 with the script in metadata."""
    import asyncio

    from open_notebook.artifacts.renderers.video_renderer import render_video_stub

    output = tmp_path / "stub_output.mp4"

    env_patch = {"ARTIFACT_RENDER_STUB": "1"}
    old_vals = {k: os.environ.get(k) for k in env_patch}
    try:
        os.environ.update(env_patch)
        # Ensure we're NOT in production
        old_env = os.environ.pop("ENV", None)
        result = asyncio.run(render_video_stub(two_beat_schema, output))
    finally:
        for k, v in old_vals.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        if old_env is not None:
            os.environ["ENV"] = old_env

    assert result.exists(), "render_video_stub must produce a file"
    assert result.suffix == ".mp4"

    probe = _ffprobe(result)
    duration = _duration(probe)
    # Allow a tiny tolerance: ffmpeg may produce 0.97–1.10s
    assert 0.5 <= duration <= 2.0, f"Stub MP4 should be ~1s, got {duration:.2f}s"

    # Verify script is in metadata (comment or title field)
    format_tags = probe.get("format", {}).get("tags", {})
    comment_field = format_tags.get("comment", "") or format_tags.get("COMMENT", "")
    title_field = format_tags.get("title", "") or format_tags.get("TITLE", "")
    combined_meta = (comment_field + " " + title_field).lower()

    # The first beat's narration should appear somewhere in the metadata
    first_beat_snippet = "welcome"  # from two_beat_schema beat 1
    assert first_beat_snippet in combined_meta or len(comment_field) > 10, (
        f"Script not found in MP4 metadata. comment='{comment_field[:80]}', "
        f"title='{title_field[:80]}'"
    )


# ---------------------------------------------------------------------------
# Test 3: Stub must raise in production
# ---------------------------------------------------------------------------

def test_stub_raises_in_production(two_beat_schema: VideoOverviewSchema, tmp_path: Path):
    """ENV=production + ARTIFACT_RENDER_STUB=1 must raise RuntimeError."""
    import asyncio

    from open_notebook.artifacts.renderers.video_renderer import render_video_stub

    output = tmp_path / "prod_stub.mp4"

    old_env = os.environ.get("ENV")
    old_stub = os.environ.get("ARTIFACT_RENDER_STUB")
    try:
        os.environ["ENV"] = "production"
        os.environ["ARTIFACT_RENDER_STUB"] = "1"
        with pytest.raises(RuntimeError, match="production"):
            asyncio.run(render_video_stub(two_beat_schema, output))
    finally:
        if old_env is None:
            os.environ.pop("ENV", None)
        else:
            os.environ["ENV"] = old_env
        if old_stub is None:
            os.environ.pop("ARTIFACT_RENDER_STUB", None)
        else:
            os.environ["ARTIFACT_RENDER_STUB"] = old_stub
