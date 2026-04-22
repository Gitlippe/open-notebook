"""Unit tests: router contract assertions for /api/artifacts/* endpoints.

These tests run fully offline — no SurrealDB, no real LLM calls, no network.
They validate:
1. Registered artifact-type count (14 expected).
2. Path-traversal guard (GET /api/artifacts/download → 403 outside root).
3. 404 for a nonexistent file inside root.
4. POST /api/artifacts/generate — error path and valid submit path.
5. GET /api/artifacts/jobs/{job_id} — mocked status response shape.
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helper: build a TestClient without triggering the DB lifespan
# ---------------------------------------------------------------------------


def _make_client(raise_server_exceptions: bool = False):
    """Return a FastAPI TestClient with the DB lifespan patched out."""
    # Patch the lifespan so AsyncMigrationManager doesn't try to connect.
    with patch("api.main.AsyncMigrationManager"):
        import api.main  # noqa: F401 — registers all routers
        from api.main import app
        from fastapi.testclient import TestClient

        return TestClient(app, raise_server_exceptions=raise_server_exceptions)


# ---------------------------------------------------------------------------
# 1. Available types — count + structure
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAvailableTypes:
    """Tests for the artifact-type registry (offline, no HTTP)."""

    def test_14_types_registered(self) -> None:
        """list_artifact_types() must return exactly 14 entries."""
        from open_notebook.artifacts import list_artifact_types

        types = list_artifact_types()
        assert len(types) == 14, (
            f"Expected 14 registered artifact types, got {len(types)}. "
            f"Types: {[t['type'] for t in types]}"
        )

    def test_all_types_have_type_and_description(self) -> None:
        """Every entry must have non-empty 'type' and 'description' keys."""
        from open_notebook.artifacts import list_artifact_types

        for entry in list_artifact_types():
            assert "type" in entry and entry["type"], (
                f"Missing 'type' in entry: {entry}"
            )
            assert "description" in entry and entry["description"], (
                f"Missing 'description' for type {entry.get('type')!r}"
            )

    def test_known_types_present(self) -> None:
        """Spot-check that key types are registered."""
        from open_notebook.artifacts import list_artifact_types

        registered = {t["type"] for t in list_artifact_types()}
        expected = {
            "briefing", "faq", "flashcards", "mindmap", "quiz",
            "study_guide", "timeline", "slide_deck", "pitch_deck",
            "research_review", "infographic", "paper_figure",
            "data_tables", "video_overview",
        }
        missing = expected - registered
        assert not missing, f"Missing artifact types: {missing}"


# ---------------------------------------------------------------------------
# 2. GET /api/artifacts/types — HTTP level
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTypesEndpoint:
    """HTTP-level tests for GET /api/artifacts/types."""

    def test_returns_200_with_14_types(self) -> None:
        client = _make_client()
        response = client.get("/api/artifacts/types")
        assert response.status_code == 200, response.text
        data = response.json()
        assert "types" in data
        assert len(data["types"]) == 14, (
            f"Expected 14 types, got {len(data['types'])}"
        )


# ---------------------------------------------------------------------------
# 3. GET /api/artifacts/download — path-traversal + 404
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDownloadEndpoint:
    """Path-traversal guard and 404 tests for the download endpoint."""

    def test_403_for_path_outside_root(self, tmp_path: Path) -> None:
        """A resolved path outside ARTIFACT_OUTPUT_ROOT must return 403."""
        # Create a real file outside the root so strict=True resolves it.
        outside_file = tmp_path / "outside.txt"
        outside_file.write_text("secret")

        root_dir = tmp_path / "artifact_root"
        root_dir.mkdir()

        import api.routers.artifacts as art_module
        import open_notebook.config as cfg_module

        with patch.dict(os.environ, {"ARTIFACT_OUTPUT_ROOT": str(root_dir)}):
            importlib.reload(cfg_module)
            importlib.reload(art_module)
            client = _make_client()
            response = client.get(
                "/api/artifacts/download",
                params={"path": str(outside_file)},
            )

        assert response.status_code == 403, (
            f"Expected 403 for path outside root, got {response.status_code}. "
            f"Response: {response.text}"
        )

    def test_404_for_nonexistent_path_inside_root(self, tmp_path: Path) -> None:
        """A non-existent path inside ARTIFACT_OUTPUT_ROOT must return 404."""
        root_dir = tmp_path / "artifact_root"
        root_dir.mkdir()
        missing_path = root_dir / "no_such_file.md"

        import api.routers.artifacts as art_module
        import open_notebook.config as cfg_module

        with patch.dict(os.environ, {"ARTIFACT_OUTPUT_ROOT": str(root_dir)}):
            importlib.reload(cfg_module)
            importlib.reload(art_module)
            client = _make_client()
            response = client.get(
                "/api/artifacts/download",
                params={"path": str(missing_path)},
            )

        assert response.status_code == 404, (
            f"Expected 404 for nonexistent file, got {response.status_code}. "
            f"Response: {response.text}"
        )


# ---------------------------------------------------------------------------
# 4. POST /api/artifacts/generate — error path + happy path
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGenerateEndpoint:
    """POST /api/artifacts/generate contract."""

    def test_missing_artifact_type_returns_422(self) -> None:
        """Payload without 'artifact_type' must fail Pydantic validation → 422."""
        client = _make_client()
        response = client.post(
            "/api/artifacts/generate",
            json={"sources": [{"title": "T", "content": "C"}]},
        )
        assert response.status_code == 422, (
            f"Expected 422 for missing artifact_type, got {response.status_code}"
        )

    def test_valid_submit_returns_job_id(self) -> None:
        """A well-formed request must call submit_command and return job_id."""
        fake_job_id = "command:unit-test-abc"

        with patch(
            "api.artifact_service.submit_command",
            return_value=fake_job_id,
        ):
            client = _make_client()
            response = client.post(
                "/api/artifacts/generate",
                json={
                    "artifact_type": "briefing",
                    "sources": [{"title": "T", "content": "C"}],
                },
            )

        assert response.status_code == 200, (
            f"Expected 200 from generate, got {response.status_code}. "
            f"Response: {response.text}"
        )
        data = response.json()
        assert data["job_id"] == fake_job_id
        assert data["status"] == "submitted"

    def test_service_error_propagates_as_5xx(self) -> None:
        """If submit_command raises, the endpoint should return ≥400."""
        from fastapi import HTTPException

        with patch(
            "api.artifact_service.submit_command",
            side_effect=RuntimeError("queue down"),
        ):
            client = _make_client()
            response = client.post(
                "/api/artifacts/generate",
                json={
                    "artifact_type": "briefing",
                    "sources": [{"title": "T", "content": "C"}],
                },
            )

        assert response.status_code >= 400, (
            f"Expected ≥400 on service error, got {response.status_code}"
        )


# ---------------------------------------------------------------------------
# 5. GET /api/artifacts/jobs/{job_id}
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestJobStatusEndpoint:
    """GET /api/artifacts/jobs/{job_id} contract."""

    def test_job_status_returns_correct_shape(self) -> None:
        """Mocked get_command_status should propagate through service to response."""
        fake_result = MagicMock()
        fake_result.status = "completed"
        fake_result.result = {
            "artifact_type": "briefing",
            "title": "My Briefing",
            "summary": "A brief summary.",
            "structured": {"sections": []},
            "files": [{"path": "/tmp/out.md", "mime_type": "text/markdown", "description": ""}],
            "metadata": {},
            "provenance": None,
            "generated_at": "2026-04-22T00:00:00+00:00",
        }
        fake_result.error_message = None

        with patch(
            "api.artifact_service.get_command_status",
            new=AsyncMock(return_value=fake_result),
        ):
            client = _make_client()
            response = client.get("/api/artifacts/jobs/command:test-123")

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["status"] == "completed"
        assert data["artifact_type"] == "briefing"
        assert data["title"] == "My Briefing"
        assert isinstance(data["files"], list) and len(data["files"]) == 1
