"""Shared helpers for Open Notebook artifact agent demos.

Each demo exercises the *real* SOTA pipeline:

    Phase 1: claim extraction (structured Pydantic output)
    Phase 2: structured draft
    Phase 3: self-critique (pointing at source vs draft)
    Phase 4: refinement applying the critique

When a provider key is configured in the environment (OPENAI_API_KEY,
ANTHROPIC_API_KEY, etc.) the demos use a real LLM. Otherwise they use
the StructuredMockChat backend, which implements the same structured-
output protocol so the workflow code path is identical.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_WORKSPACE = Path(__file__).resolve().parent.parent
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))

from open_notebook.artifacts import ArtifactResult, generate_artifact  # noqa: E402
from open_notebook.artifacts.llm import _has_provider_configured  # noqa: E402


DEMO_OUTPUT_ROOT = Path(__file__).resolve().parent / "_output"


def demo_output_dir(name: str) -> str:
    out = DEMO_OUTPUT_ROOT / name
    out.mkdir(parents=True, exist_ok=True)
    return str(out)


def banner(name: str, artifact: str) -> None:
    print()
    print("=" * 72)
    print(f"DEMO: {name}")
    print(f"ARTIFACT TYPE: {artifact}")
    print("=" * 72)


def print_result(result: ArtifactResult, truncate: int = 320) -> None:
    print(f"\nTitle:    {result.title}")
    if result.summary:
        summary = result.summary
        if len(summary) > truncate:
            summary = summary[:truncate] + "..."
        print(f"Summary:  {summary}")
    print(f"Pipeline: {result.metadata.get('pipeline', '—')}")
    print("Files:")
    for f in result.files:
        p = Path(f.path)
        size = p.stat().st_size if p.exists() else 0
        print(f"  - {p.name}  ({f.mime_type}, {size:,} bytes)")
    # Show select metadata, not everything
    meta = {k: v for k, v in result.metadata.items() if k != "pipeline"}
    if meta:
        print(f"Metadata: {meta}")


def backend_label() -> str:
    return "LLM (env provider)" if _has_provider_configured() else "StructuredMockChat (offline)"


async def run_demo(
    name: str,
    artifact_type: str,
    sources,
    *,
    title: str | None = None,
    config: dict | None = None,
):
    banner(name, artifact_type)
    print(f"Backend: {backend_label()}")
    result = await generate_artifact(
        artifact_type=artifact_type,
        sources=sources,
        title=title,
        config=config or {},
        output_dir=demo_output_dir(name),
    )
    print_result(result)
    return result
