"""Dead-code lint: prove the heuristic fallback is gone.

This is the first of three "no fake output" guards from the plan:
1. Dead-code lint (this file) — AST scan asserting no imports/references.
2. LLM call counter — provenance-based assertion in integration tests.
3. Provenance metadata — ArtifactResult.provenance.calls non-empty.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ARTIFACTS_ROOT = Path(__file__).resolve().parents[3] / "open_notebook" / "artifacts"


pytestmark = pytest.mark.unit


def test_heuristic_module_does_not_exist() -> None:
    """heuristic.py must be gone from the artifacts package."""
    path = ARTIFACTS_ROOT / "heuristic.py"
    assert not path.exists(), (
        f"{path} must not exist. The SOTA rebuild removed the heuristic "
        f"fallback entirely; any 'real_llm unavailable' path should raise "
        f"ExternalServiceError so the job queue retries it."
    )


def test_no_heuristic_imports_in_artifacts_package() -> None:
    """No module under open_notebook/artifacts imports heuristic.*"""
    offenders: list[str] = []
    for py in ARTIFACTS_ROOT.rglob("*.py"):
        try:
            tree = ast.parse(py.read_text())
        except SyntaxError as exc:  # pragma: no cover - syntax errors fail elsewhere
            offenders.append(f"{py}: {exc}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if "heuristic" in node.module and "artifacts" in (node.module or ""):
                    offenders.append(f"{py}: from {node.module} import ...")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("open_notebook.artifacts.heuristic"):
                        offenders.append(f"{py}: import {alias.name}")
    assert not offenders, (
        "Heuristic imports must not exist in open_notebook/artifacts.\n  "
        + "\n  ".join(offenders)
    )


def test_no_heuristic_function_references() -> None:
    """Source-level grep for heuristic_json / _heuristic_text / heuristic fallback."""
    banned_names = {"heuristic_json", "_heuristic_text"}
    offenders: list[str] = []
    for py in ARTIFACTS_ROOT.rglob("*.py"):
        text = py.read_text()
        for name in banned_names:
            if name in text:
                offenders.append(f"{py}: references {name}")
    assert not offenders, (
        "Heuristic function references must not exist in the artifacts "
        "package:\n  " + "\n  ".join(offenders)
    )


def test_no_artifact_use_llm_gate() -> None:
    """ARTIFACT_USE_LLM must not appear in product code — LLM is the only path."""
    offenders: list[str] = []
    for py in ARTIFACTS_ROOT.rglob("*.py"):
        text = py.read_text()
        if "ARTIFACT_USE_LLM" in text:
            offenders.append(str(py))
    assert not offenders, (
        "ARTIFACT_USE_LLM gate must be deleted; LLM is the only code path.\n"
        "Offenders:\n  " + "\n  ".join(offenders)
    )


def test_no_silent_content_truncation_in_base() -> None:
    """combined_content must not accept a max_chars parameter anymore.

    Long inputs must flow through ``chunked_generate()`` instead of silent
    truncation; see ``BaseArtifactGenerator.chunked_generate``.
    """
    base_py = (ARTIFACTS_ROOT / "base.py").read_text()
    tree = ast.parse(base_py)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "combined_content":
            # Only accepts ``self`` argument now.
            args = node.args
            param_names = [a.arg for a in args.args if a.arg != "self"]
            assert not param_names, (
                f"combined_content must take no parameters besides self; "
                f"found {param_names}. Long content must go through "
                f"chunked_generate() instead of silent truncation."
            )
            break
    else:
        raise AssertionError(
            "combined_content method not found on ArtifactRequest in base.py"
        )
