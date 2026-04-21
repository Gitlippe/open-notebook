"""Shared helpers for Open Notebook artifact agent demos."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the workspace root importable when running demos standalone.
_WORKSPACE = Path(__file__).resolve().parent.parent
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))

from open_notebook.artifacts import ArtifactResult, generate_artifact  # noqa: E402


DEMO_OUTPUT_ROOT = Path(__file__).resolve().parent / "_output"


def demo_output_dir(name: str) -> str:
    out = DEMO_OUTPUT_ROOT / name
    out.mkdir(parents=True, exist_ok=True)
    return str(out)


def banner(name: str, artifact: str) -> None:
    print("=" * 72)
    print(f"DEMO: {name}")
    print(f"ARTIFACT TYPE: {artifact}")
    print("=" * 72)


def print_result(result: ArtifactResult, truncate: int = 240) -> None:
    print(f"\nArtifact: {result.artifact_type}")
    print(f"Title:    {result.title}")
    if result.summary:
        summary = result.summary
        if len(summary) > truncate:
            summary = summary[:truncate] + "..."
        print(f"Summary:  {summary}")
    print("Files:")
    for f in result.files:
        p = Path(f.path)
        size = p.stat().st_size if p.exists() else 0
        print(f"  - {f.path}  [{f.mime_type}, {size} bytes]")
    if result.metadata:
        print(f"Metadata: {result.metadata}")
    print()


def offline_mode() -> bool:
    return os.environ.get("ARTIFACT_USE_LLM", "0") not in {"1", "true", "yes", "on"}


async def run_demo(
    name: str,
    artifact_type: str,
    sources,
    *,
    title: str | None = None,
    config: dict | None = None,
):
    banner(name, artifact_type)
    if offline_mode():
        print("(Running in offline mode — using heuristic extractor. "
              "Set ARTIFACT_USE_LLM=1 + a provider key to use an LLM.)")
    result = await generate_artifact(
        artifact_type=artifact_type,
        sources=sources,
        title=title,
        config=config or {},
        output_dir=demo_output_dir(name),
    )
    print_result(result)
    return result
