"""Shared fixtures for artifact-generator tests.

Tests run against :class:`StructuredMockChat` — the same offline backend
used by the generators when no API provider is configured. This means
tests exercise the full claim-extraction → draft → critique → refine
pipeline without touching the network.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from open_notebook.artifacts import (
    ArtifactLLM,
    ArtifactSource,
    StructuredMockChat,
    use_artifact_llm,
)


SAMPLE_TEXT = """Title: Training-Free GRPO.
Authors: Yuzheng Cai, Siqi Cai, Yuchen Shi, Zihan Xu.
Affiliations: Tencent Youtu Lab, Fudan University, Xiamen University.

The paper proposes Training-Free GRPO, doing GRPO-style RL optimization
through prompt engineering instead of parameter updates. The method
generates multiple rollouts per query, uses the LLM to introspect on
successes and failures, and extracts natural language experiences.

On AIME 2024 they improve DeepSeek-V3.1-Terminus from 80.0 to 82.7
with just 100 training samples. They claim 100x less data and 500x
lower cost than fine-tuning 32B models.

Limitation: the authors never compare their method to traditional GRPO
on the same base model. Published October 9, 2025 on arXiv.
"""


@pytest.fixture
def mock_llm() -> ArtifactLLM:
    return ArtifactLLM(chat=StructuredMockChat())


@pytest.fixture(autouse=True)
def _install_default_mock_llm(mock_llm):
    """Make ``ArtifactLLM.current()`` return the mock by default in tests."""
    with use_artifact_llm(mock_llm):
        yield


@pytest.fixture
def sample_source() -> ArtifactSource:
    return ArtifactSource(title="Training-Free GRPO", content=SAMPLE_TEXT)


@pytest.fixture
def sample_sources(sample_source) -> list[ArtifactSource]:
    return [sample_source]


@pytest.fixture
def output_dir(tmp_path: Path) -> str:
    return str(tmp_path / "artifacts")
