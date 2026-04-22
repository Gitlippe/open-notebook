"""Integration tests for image_gen.py.

Markers:
- The ``real_llm`` tests require ``OPENAI_API_KEY`` or ``GOOGLE_API_KEY``.
  They are skipped automatically when no key is present.
- The ``integration`` tests that don't need a real key cover the
  ConfigurationError path and the log-emission contract.

Tests:
1. ``real_llm``: Request a 512×512 image, assert PNG bytes returned and
   ``image_gen_call`` log record emitted with required fields.
2. ``integration``: Verify ConfigurationError is raised when no key is found.
3. ``integration``: Verify generate_image_to_file writes a valid PNG.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_openai_key() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


# ---------------------------------------------------------------------------
# Tests that don't need a real API key
# ---------------------------------------------------------------------------


class TestConfigurationError:
    @pytest.mark.asyncio
    async def test_raises_config_error_without_key(self) -> None:
        """generate_image must raise ConfigurationError when no key is found."""
        from open_notebook.artifacts.image_gen import generate_image
        from open_notebook.exceptions import ConfigurationError

        # Patch _resolve_api_key to raise ConfigurationError directly
        with patch(
            "open_notebook.artifacts.image_gen._resolve_api_key",
            side_effect=ConfigurationError("no key"),
        ):
            with pytest.raises(ConfigurationError, match="no key"):
                await generate_image("a photo of a test pattern")


class TestLogEmission:
    @pytest.mark.asyncio
    async def test_log_record_emitted_on_success(self) -> None:
        """A structured image_gen_call log record must be emitted on success."""
        from open_notebook.artifacts.image_gen import generate_image

        captured_logs: list[dict] = []

        def _sink(message) -> None:
            record = message.record
            if record["extra"].get("image_gen_call"):
                try:
                    captured_logs.append(json.loads(record["message"]))
                except json.JSONDecodeError:
                    pass

        # Patch out the actual API call and key resolution
        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        with (
            patch(
                "open_notebook.artifacts.image_gen._resolve_api_key",
                return_value="test-key",
            ),
            patch(
                "open_notebook.artifacts.image_gen._generate_via_openai",
                new=AsyncMock(return_value=fake_png),
            ),
        ):
            from loguru import logger

            logger.add(_sink, level="INFO")
            result = await generate_image("a colorful test pattern", size="256x256")
            logger.remove()

        assert result == fake_png
        assert len(captured_logs) == 1, (
            f"Expected exactly 1 log record, got {len(captured_logs)}"
        )
        log = captured_logs[0]
        assert "provider" in log
        assert "model" in log
        assert "prompt_hash" in log
        assert "latency_ms" in log
        assert "status" in log
        assert log["status"] == "ok"

    @pytest.mark.asyncio
    async def test_log_record_emitted_on_error(self) -> None:
        """A log record with status='error' is emitted when generation fails."""
        from open_notebook.artifacts.image_gen import generate_image
        from open_notebook.exceptions import ExternalServiceError

        captured_logs: list[dict] = []

        def _sink(message) -> None:
            record = message.record
            if record["extra"].get("image_gen_call"):
                try:
                    captured_logs.append(json.loads(record["message"]))
                except json.JSONDecodeError:
                    pass

        with (
            patch(
                "open_notebook.artifacts.image_gen._resolve_api_key",
                return_value="test-key",
            ),
            patch(
                "open_notebook.artifacts.image_gen._generate_via_openai",
                side_effect=ExternalServiceError("API error"),
            ),
        ):
            from loguru import logger

            logger.add(_sink, level="INFO")
            with pytest.raises(ExternalServiceError):
                await generate_image("failing prompt")
            logger.remove()

        assert len(captured_logs) == 1
        assert captured_logs[0]["status"] == "error"
        assert captured_logs[0]["error_class"] is not None


class TestGenerateImageToFile:
    @pytest.mark.asyncio
    async def test_writes_png_to_file(self, tmp_path: Path) -> None:
        """generate_image_to_file must create the output file with PNG content."""
        from open_notebook.artifacts.image_gen import generate_image_to_file

        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 200
        output = tmp_path / "subdir" / "image.png"

        with (
            patch(
                "open_notebook.artifacts.image_gen._resolve_api_key",
                return_value="test-key",
            ),
            patch(
                "open_notebook.artifacts.image_gen._generate_via_openai",
                new=AsyncMock(return_value=fake_png),
            ),
        ):
            result = await generate_image_to_file("a mountain landscape", output)

        assert result == output
        assert output.exists()
        assert output.read_bytes() == fake_png
        assert output.parent.exists()


# ---------------------------------------------------------------------------
# Real LLM tests (skipped without OPENAI_API_KEY)
# ---------------------------------------------------------------------------


@pytest.mark.real_llm
@pytest.mark.skipif(not _has_openai_key(), reason="OPENAI_API_KEY not set")
class TestRealImageGeneration:
    @pytest.mark.asyncio
    async def test_returns_valid_png_bytes(self) -> None:
        """Real provider: generate_image returns valid PNG bytes."""
        from open_notebook.artifacts.image_gen import generate_image

        png_bytes = await generate_image(
            "A simple geometric test pattern, blue circles on white background",
            size="512x512",
        )

        assert isinstance(png_bytes, bytes)
        assert len(png_bytes) > 1000, "PNG should be > 1 KB"
        # PNG magic bytes
        assert png_bytes[:4] == b"\x89PNG", (
            "Returned bytes are not a PNG (wrong magic bytes)"
        )

    @pytest.mark.asyncio
    async def test_generate_image_to_file_real(self, tmp_path: Path) -> None:
        """Real provider: generate_image_to_file writes a valid PNG."""
        from PIL import Image
        from open_notebook.artifacts.image_gen import generate_image_to_file

        output = tmp_path / "real_image.png"
        result = await generate_image_to_file(
            "A minimal flat-design icon of a notebook",
            output,
            size="512x512",
        )

        assert result.exists()
        img = Image.open(result)
        img.verify()
