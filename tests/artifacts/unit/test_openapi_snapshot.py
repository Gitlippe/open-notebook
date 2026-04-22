"""OpenAPI snapshot tests for /api/artifacts/* endpoints.

These tests validate two things:
1. Structural checks: expected paths, request/response schemas present.
2. Snapshot match: generated spec matches the golden file in
   ``tests/artifacts/reference/artifact_openapi.json``.

Refreshing the snapshot
-----------------------
Run with ``--refresh-openapi`` to regenerate the golden file when the
contract intentionally changes::

    uv run pytest tests/artifacts/unit/test_openapi_snapshot.py --refresh-openapi

This updates ``artifact_openapi.json`` and the test passes. Commit the
updated file to document the intentional contract change.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest

# Reference file lives in tests/artifacts/reference/ (one level up from unit/)
_REFERENCE_FILE = (
    Path(__file__).resolve().parents[1] / "reference" / "artifact_openapi.json"
)

_EXPECTED_PATHS = {
    "/api/artifacts/types",
    "/api/artifacts/generate",
    "/api/artifacts/jobs/{job_id}",
    "/api/artifacts/download",
}

_EXPECTED_SCHEMAS = {
    "ArtifactGenerateRequest",
    "ArtifactJobSubmitted",
    "ArtifactJobResult",
    "ArtifactSourceIn",
}


def _generate_artifact_spec() -> Dict[str, Any]:
    """Generate the OpenAPI spec filtered to /api/artifacts paths."""
    with patch("api.main.AsyncMigrationManager"):
        import api.main  # noqa: F401 — triggers route registration
        from api.main import app

        spec = app.openapi()

    artifact_paths = {
        k: v for k, v in spec.get("paths", {}).items()
        if k.startswith("/api/artifacts")
    }
    artifact_spec: Dict[str, Any] = {
        "openapi": spec["openapi"],
        "info": spec["info"],
        "paths": artifact_paths,
    }

    # Resolve only schemas referenced by artifact paths (recursively)
    all_schemas = spec.get("components", {}).get("schemas", {})
    paths_str = json.dumps(artifact_paths)
    used: set[str] = set(re.findall(r"#/components/schemas/([A-Za-z0-9_]+)", paths_str))
    to_check = set(used)
    while to_check:
        name = to_check.pop()
        if name not in all_schemas:
            continue
        nested = set(
            re.findall(r"#/components/schemas/([A-Za-z0-9_]+)", json.dumps(all_schemas[name]))
        )
        new_ones = nested - used
        used |= new_ones
        to_check |= new_ones

    artifact_spec["components"] = {
        "schemas": {k: v for k, v in all_schemas.items() if k in used}
    }
    return artifact_spec


# ---------------------------------------------------------------------------
# CLI hook
# ---------------------------------------------------------------------------


def pytest_addoption(parser):  # type: ignore[override]
    """Add --refresh-openapi flag for snapshot regeneration."""
    try:
        parser.addoption(
            "--refresh-openapi",
            action="store_true",
            default=False,
            help="Regenerate the artifact OpenAPI reference snapshot.",
        )
    except ValueError:
        pass  # Option already registered (pytest reuse)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOpenAPISnapshot:
    """Structural + snapshot tests for the /api/artifacts/* OpenAPI spec."""

    @pytest.fixture(scope="class")
    def spec(self) -> Dict[str, Any]:
        return _generate_artifact_spec()

    def test_spec_has_openapi_version(self, spec: Dict[str, Any]) -> None:
        assert "openapi" in spec
        assert spec["openapi"].startswith("3.")

    def test_expected_artifact_paths_present(self, spec: Dict[str, Any]) -> None:
        actual = set(spec.get("paths", {}).keys())
        missing = _EXPECTED_PATHS - actual
        assert not missing, (
            f"Missing artifact paths in OpenAPI spec: {missing}\n"
            f"Actual paths: {sorted(actual)}"
        )

    def test_no_non_artifact_paths(self, spec: Dict[str, Any]) -> None:
        """Filtered spec must contain only /api/artifacts/* paths."""
        for path in spec.get("paths", {}):
            assert path.startswith("/api/artifacts"), (
                f"Non-artifact path leaked into filtered spec: {path}"
            )

    def test_expected_schemas_present(self, spec: Dict[str, Any]) -> None:
        actual_schemas = set(spec.get("components", {}).get("schemas", {}).keys())
        missing = _EXPECTED_SCHEMAS - actual_schemas
        assert not missing, (
            f"Missing schemas in artifact OpenAPI spec: {missing}\n"
            f"Actual schemas: {sorted(actual_schemas)}"
        )

    def test_generate_endpoint_has_post(self, spec: Dict[str, Any]) -> None:
        generate_path = spec.get("paths", {}).get("/api/artifacts/generate", {})
        assert "post" in generate_path, (
            "POST method missing from /api/artifacts/generate"
        )

    def test_snapshot_matches_reference(
        self, spec: Dict[str, Any], request: pytest.FixtureRequest
    ) -> None:
        """Compare generated spec against golden file.

        Run with ``--refresh-openapi`` to regenerate the golden file.
        """
        if request.config.getoption("--refresh-openapi", default=False):
            _REFERENCE_FILE.parent.mkdir(parents=True, exist_ok=True)
            _REFERENCE_FILE.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
            pytest.skip("Refreshed OpenAPI snapshot — commit the updated reference file.")

        assert _REFERENCE_FILE.exists(), (
            f"Reference file missing: {_REFERENCE_FILE}\n"
            "Run with --refresh-openapi to generate it."
        )
        reference = json.loads(_REFERENCE_FILE.read_text(encoding="utf-8"))

        if spec != reference:
            import difflib

            current_str = json.dumps(spec, indent=2, sort_keys=True)
            reference_str = json.dumps(reference, indent=2, sort_keys=True)
            diff = "\n".join(
                difflib.unified_diff(
                    reference_str.splitlines(),
                    current_str.splitlines(),
                    fromfile="reference (golden)",
                    tofile="current (generated)",
                    lineterm="",
                )
            )
            pytest.fail(
                f"OpenAPI snapshot mismatch. If this is an intentional change, "
                f"run with --refresh-openapi.\n\nDiff:\n{diff}"
            )
