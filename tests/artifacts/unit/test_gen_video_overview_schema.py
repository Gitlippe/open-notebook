"""Unit tests for VideoOverviewGenerator — schema, registry, and config contract."""
from __future__ import annotations
import pytest
from open_notebook.artifacts.generators.video_overview import (
    BeatSchema, VideoOverviewGenerator, VideoOverviewSchema, VoiceMetadataSchema,
)
from open_notebook.artifacts.registry import ARTIFACT_TYPES

pytestmark = pytest.mark.unit


class TestVideoOverviewSchema:
    def test_schema_has_title(self):
        assert "title" in VideoOverviewSchema.model_fields

    def test_schema_has_total_duration_seconds(self):
        assert "total_duration_seconds" in VideoOverviewSchema.model_fields

    def test_schema_has_beats(self):
        assert "beats" in VideoOverviewSchema.model_fields

    def test_schema_has_voice(self):
        assert "voice" in VideoOverviewSchema.model_fields

    def test_beat_schema_has_narration_script(self):
        assert "narration_script" in BeatSchema.model_fields

    def test_beat_schema_has_visual_prompt(self):
        assert "visual_prompt" in BeatSchema.model_fields

    def test_beat_schema_has_alt_text(self):
        assert "alt_text" in BeatSchema.model_fields

    def test_beat_schema_has_duration_seconds(self):
        assert "duration_seconds" in BeatSchema.model_fields

    def test_beat_schema_has_beat_index(self):
        assert "beat_index" in BeatSchema.model_fields

    def test_voice_schema_fields(self):
        fields = VoiceMetadataSchema.model_fields
        assert "provider" in fields
        assert "voice_id" in fields
        assert "speaking_rate" in fields

    def test_voice_provider_literal(self):
        v = VoiceMetadataSchema(provider="elevenlabs", voice_id="rachel", speaking_rate=1.0)
        assert v.provider == "elevenlabs"

    def test_voice_invalid_provider_rejected(self):
        with pytest.raises(Exception):
            VoiceMetadataSchema(provider="aws_polly", voice_id="Joanna", speaking_rate=1.0)  # type: ignore

    def test_beat_duration_bounds(self):
        beat = BeatSchema(
            beat_index=1, duration_seconds=30,
            narration_script="Hello world.", visual_prompt="A bright scene.",
            alt_text="A beautiful landscape.",
        )
        assert beat.duration_seconds == 30

    def test_beat_duration_below_min_rejected(self):
        with pytest.raises(Exception):
            BeatSchema(beat_index=1, duration_seconds=2, narration_script=".", visual_prompt=".", alt_text=".")

    def test_schema_validates_full_spec(self):
        spec = VideoOverviewSchema(
            title="Understanding AI", total_duration_seconds=90,
            voice=VoiceMetadataSchema(provider="openai", voice_id="nova", speaking_rate=1.0),
            beats=[
                BeatSchema(beat_index=1, duration_seconds=30,
                           narration_script="Welcome to this video on AI.",
                           visual_prompt="A futuristic city at dawn, photorealistic.",
                           alt_text="Futuristic city skyline at dawn."),
                BeatSchema(beat_index=2, duration_seconds=60,
                           narration_script="Let's explore the key concepts.",
                           visual_prompt="Abstract network of glowing nodes.",
                           alt_text="Glowing neural network visualization."),
            ],
        )
        assert spec.total_duration_seconds == 90
        assert len(spec.beats) == 2

    def test_schema_round_trips(self):
        spec = VideoOverviewSchema(
            title="Test Video", total_duration_seconds=45,
            beats=[BeatSchema(beat_index=1, duration_seconds=45,
                              narration_script="Narration.", visual_prompt="Visual.", alt_text="Alt.")],
        )
        restored = VideoOverviewSchema.model_validate(spec.model_dump())
        assert restored.title == "Test Video"
        assert restored.beats[0].narration_script == "Narration."


class TestVideoOverviewGeneratorRegistry:
    def test_generator_registered(self):
        assert "video_overview" in ARTIFACT_TYPES

    def test_registered_class_is_video_overview_generator(self):
        assert ARTIFACT_TYPES["video_overview"] is VideoOverviewGenerator


class TestVideoOverviewGeneratorConfig:
    def test_default_model_type_is_set(self):
        assert VideoOverviewGenerator.default_model_type
        assert isinstance(VideoOverviewGenerator.default_model_type, str)

    def test_artifact_type_is_video_overview(self):
        assert VideoOverviewGenerator.artifact_type == "video_overview"

    def test_description_is_non_empty(self):
        assert VideoOverviewGenerator.description

    def test_description_mentions_phase2(self):
        desc_lower = VideoOverviewGenerator.description.lower()
        assert "phase 2" in desc_lower or "stream g" in desc_lower or "tts" in desc_lower
