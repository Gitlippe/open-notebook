"""Cross-provider matrix test — pre-merge blocking gate.

Per the plan (§ Test Tiers / Cross-provider matrix), we exercise 3
representative artifact types against 3 different providers to catch
structured-output drift. If any cell fails, the merge is blocked.

The matrix is deliberately small (9 cells) to stay under 10 minutes even
when every cell hits a real LLM. Full 14 × 3 coverage is in the nightly
eval suite.

Skip behaviour:
- If a specific provider's key is missing, only its three cells skip.
- No special handling for SurrealDB: we mock ``provision_langchain_model``
  to return a LangChain model built directly from env keys (see conftest).

Artifact choice rationale:
- **slide_deck**: exercises pptx + chart renderers + long structured output.
- **flashcards**: exercises anki renderer + nested list schema (tags).
- **research_review**: exercises deeply nested schema (why_we_care, resources).

Provider choice:
- **anthropic/claude-sonnet-4-6** — tool-use structured output.
- **openai/gpt-4o-mini** — native json_schema strict mode (cheap for matrix).
- **openrouter/openai/gpt-4o-mini** — OpenRouter passthrough; also confirms
  OpenRouter routing works end-to-end.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from open_notebook.artifacts.base import ArtifactRequest, ArtifactSource
from open_notebook.artifacts.registry import get_generator

from .conftest import VALID_PROVIDERS, langchain_model_for_provider

pytestmark = [pytest.mark.integration, pytest.mark.real_llm, pytest.mark.matrix]


SAMPLE_CONTENT = """The emergence of Training-Free GRPO represents a
pragmatic pivot in reinforcement-learning-from-reward research. Rather
than updating model weights with policy-gradient methods, the technique
distils the reward signal into a natural-language experience buffer that
is injected into the prompt at inference time. On AIME 2024, this lifts
DeepSeek-V3.1 from 80.0 to 82.7 with only 100 training samples, roughly
a 100x data-efficiency improvement over conventional fine-tuning. The
authors do not, however, compare against traditional GRPO on the same
base model, which limits the inferential weight of their efficiency
claim. Notable methodological risks include experience-buffer bloat,
prompt fragility across model versions, and an unclear story for tasks
where rewards are sparse or delayed."""


# (env-var name that gates this provider, model_id passed to LangChain builder).
PROVIDER_MATRIX: list[tuple[str, str]] = [
    ("ANTHROPIC_API_KEY", "anthropic/claude-haiku-4-5-20251001"),
    ("OPENAI_API_KEY", "openai/gpt-4o-mini"),
    ("OPENROUTER_API_KEY", "openrouter/openai/gpt-4o-mini"),
]

ARTIFACT_MATRIX = ["slide_deck", "flashcards", "research_review"]


@pytest.mark.parametrize(
    ("env_var", "model_id"),
    PROVIDER_MATRIX,
    ids=[p[1].split("/", 1)[0] for p in PROVIDER_MATRIX],
)
@pytest.mark.parametrize("artifact_type", ARTIFACT_MATRIX)
async def test_matrix_cell(
    env_var: str,
    model_id: str,
    artifact_type: str,
    tmp_path: Path,
) -> None:
    """One cell in the (artifact_type × provider) matrix.

    Asserts:
    - The generator completes without raising.
    - Output has at least one file on disk.
    - ``provenance.calls`` has at least one entry.
    - The provider recorded in provenance is a real provider (not ``injected``
      — that would mean the test accidentally used a stubbed generator).

    Skips if the target provider key is not set.
    """
    real_model = langchain_model_for_provider(env_var, model_id)

    generator = get_generator(artifact_type)
    request = ArtifactRequest(
        artifact_type=artifact_type,
        title=f"matrix-{artifact_type}-{model_id.split('/', 1)[0]}",
        sources=[ArtifactSource(title="Training-Free GRPO", content=SAMPLE_CONTENT)],
        config={"max_items": 3},
        output_dir=str(tmp_path),
    )

    with patch(
        "open_notebook.ai.provision.provision_langchain_model",
        new=AsyncMock(return_value=real_model),
    ):
        result = await generator.generate(request)

    assert result.artifact_type == artifact_type
    assert result.files, f"{artifact_type} x {model_id}: no files rendered"
    assert any(
        Path(f.path).exists() for f in result.files
    ), f"{artifact_type} x {model_id}: no rendered file exists on disk"

    # Provenance proof — the linchpin of the "no fake output" guard.
    assert result.provenance is not None, "ArtifactResult missing provenance"
    assert result.provenance.calls, "provenance.calls is empty — LLM was never called"

    first_call = result.provenance.calls[0]
    assert first_call.provider, "provenance.calls[0].provider is empty"

    # Reject the injected-stub fingerprint.
    assert first_call.provider.lower() != "injected", (
        f"{artifact_type} x {model_id}: provenance reports 'injected' — "
        "a stubbed generator was used instead of the real LLM"
    )

    # Recognise the provider label somewhere (LangChain naming differs across
    # providers so we allow the allowlist to match substrings).
    provider_lc = (first_call.provider or "").lower()
    assert any(v in provider_lc for v in VALID_PROVIDERS), (
        f"{artifact_type} x {model_id}: unknown provider={first_call.provider!r}"
    )

    # Token-count sanity: a real LLM call always returns >0 output tokens.
    assert (first_call.tokens_out or 0) > 0, (
        f"{artifact_type} x {model_id}: tokens_out is zero — "
        "did the LLM call actually run?"
    )
