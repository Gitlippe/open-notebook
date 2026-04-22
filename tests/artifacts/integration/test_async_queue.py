"""Integration test: async queue plumbing + end-to-end artifact generation.

Markers
-------
``integration`` + ``real_llm``: skipped when no provider keys are available.
``unit``: the command-layer wiring tests run offline.

Architecture note: surreal-commands worker feasibility
-------------------------------------------------------
The ``surreal-commands`` worker polls a **live SurrealDB instance** for pending
``command:*`` records and executes them there.  Spinning up a SurrealDB server
inside a pytest session is not currently wired — the project has no ephemeral
SurrealDB fixture and the standard CI runner does not start it.

Given this constraint the integration test validates the **same logical path**
the worker takes by calling ``artifact_service.generate()`` directly.  This
function is the exact call the worker makes inside the command handler
(see ``commands/artifact_commands.py:generate_artifact_command``).

Additionally, ``provision_langchain_model`` normally reads the default model
configuration from **SurrealDB** (via ``model_manager.get_default_model``).
Since no DB is available in the test environment, we mock
``open_notebook.ai.provision.provision_langchain_model`` to return a real
Esperanto/LangChain model built directly from env-var provider keys.  This
lets the test make real LLM API calls (tokens_out > 0, real provider) while
completely bypassing the SurrealDB dependency.

The separate ``TestCommandLayerWiring`` class (marker: ``unit``) asserts the
queue-submission path (router -> service -> submit_command) without a live DB.

Router contract assertions (path-traversal guard, 14-type list, etc.) live in
``tests/artifacts/unit/test_router_contract.py``.

Exit gate assertions covered here
----------------------------------
1. ``artifact_service.generate()`` returns ``ArtifactResult``.
2. ``result.files[0].path`` exists on disk.
3. ``result.provenance.calls[0].provider`` is in the live-provider allowlist.
4. ``result.provenance.calls[0].tokens_out > 0``.
5. Download endpoint returns 200 for the generated file (via TestClient).
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Providers we accept as valid (plan allowlist + LangChain provider name variants)
VALID_PROVIDERS = {
    "anthropic",
    "openai",
    "openrouter",
    "google",
    "xai",
    "groq",
    "mistral",
    "anthropic-chat",
    "openai-chat",
}

_SMALL_CONTENT = (
    "Title: Training-Free GRPO\n"
    "Authors: Yuzheng Cai, Siqi Cai.\n"
    "Affiliations: Tencent Youtu Lab, Fudan University, Xiamen University.\n\n"
    "The paper proposes Training-Free GRPO, doing GRPO-style RL optimisation "
    "through prompt engineering instead of parameter updates. The method "
    "generates multiple rollouts per query and uses the LLM to introspect on "
    "successes and failures.\n\n"
    "On AIME 2024 they improve DeepSeek-V3.1-Terminus from 80.0 to 82.7 "
    "with just 100 training samples."
)


def _has_provider_key() -> bool:
    """Return True if at least one LLM provider key is configured."""
    keys = [
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "GOOGLE_API_KEY",
        "XAI_API_KEY",
    ]
    return any(os.environ.get(k) for k in keys)


def _best_langchain_model():
    """Return the best available real LangChain model from env keys.

    Priority: Anthropic (cheap + good structured output) > OpenAI > OpenRouter.
    Bypasses SurrealDB entirely — used only by integration tests.
    """
    from esperanto import AIFactory

    if os.environ.get("ANTHROPIC_API_KEY"):
        m = AIFactory.create_language(
            model_name="claude-haiku-4-5-20251001", provider="anthropic"
        )
        return m.to_langchain()
    if os.environ.get("OPENAI_API_KEY"):
        m = AIFactory.create_language(model_name="gpt-4o-mini", provider="openai")
        return m.to_langchain()
    if os.environ.get("OPENROUTER_API_KEY"):
        m = AIFactory.create_language(
            model_name="openai/gpt-4o-mini", provider="openrouter"
        )
        return m.to_langchain()
    raise RuntimeError(
        "No provider key available to build a real LLM for integration test"
    )


def _make_test_client():
    """Create a FastAPI TestClient without triggering the DB lifespan."""
    import api.main  # noqa: F401 — registers routes + commands
    from api.main import app
    from fastapi.testclient import TestClient

    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Integration: real LLM end-to-end (calls artifact_service.generate directly)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.real_llm
class TestGenerateBriefingRealLLM:
    """Full integration test: generate a briefing artifact with a real LLM.

    We call ``artifact_service.generate()`` directly — the same call the
    surreal-commands worker makes — because running the worker requires a live
    SurrealDB instance which is not available in the test environment.

    ``provision_langchain_model`` is mocked to return a real Esperanto model
    built directly from env-var provider keys, so we still make real API calls
    without needing a DB-configured model record.
    """

    @pytest.fixture(autouse=True)
    def skip_without_keys(self):
        if not _has_provider_key():
            pytest.skip(
                "No LLM provider key found (checked ANTHROPIC_API_KEY, "
                "OPENAI_API_KEY, OPENROUTER_API_KEY, GOOGLE_API_KEY, XAI_API_KEY). "
                "Set at least one to run real-LLM integration tests."
            )

    @pytest.mark.asyncio
    async def test_generate_briefing_end_to_end(self, tmp_path: Path) -> None:
        """Generate a briefing artifact and assert all exit-gate conditions."""
        from api.artifact_service import generate as artifact_generate

        real_model = _best_langchain_model()
        output_root = str(tmp_path)

        with patch(
            "open_notebook.ai.provision.provision_langchain_model",
            new=AsyncMock(return_value=real_model),
        ):
            result = await artifact_generate(
                artifact_type="briefing",
                sources=[{"title": "Training-Free GRPO", "content": _SMALL_CONTENT}],
                title="Test Briefing Integration",
                output_dir=output_root,
            )

        # (a) result has the right type
        from open_notebook.artifacts.base import ArtifactResult

        assert isinstance(result, ArtifactResult)
        assert result.artifact_type == "briefing"

        # (b) primary output file exists on disk
        assert result.files, "ArtifactResult.files must not be empty"
        primary_path = Path(result.files[0].path)
        assert primary_path.exists(), (
            f"Output file does not exist: {primary_path}\n"
            f"Files reported: {result.files}"
        )

        # (c) provenance has at least one real LLM call record
        assert result.provenance is not None
        calls = result.provenance.calls
        assert len(calls) >= 1, f"Expected >= 1 LLM call in provenance, got {len(calls)}"
        provider = calls[0].provider
        assert any(v in (provider or "") for v in VALID_PROVIDERS), (
            f"provenance.calls[0].provider={provider!r} is not in the "
            f"live-provider allowlist {VALID_PROVIDERS}. "
            "Either unexpected provider or test double leaked through."
        )

        # (d) tokens_out > 0
        tokens_out = calls[0].tokens_out
        assert tokens_out is not None and tokens_out > 0, (
            f"provenance.calls[0].tokens_out={tokens_out!r} must be positive."
        )

        # (e) download endpoint returns 200
        import importlib

        import api.routers.artifacts as art_module
        import open_notebook.config as cfg_module

        with patch.dict(os.environ, {"ARTIFACT_OUTPUT_ROOT": output_root}):
            importlib.reload(cfg_module)
            importlib.reload(art_module)
            client = _make_test_client()
            response = client.get(
                "/api/artifacts/download",
                params={"path": str(primary_path)},
            )
        assert response.status_code == 200, (
            f"Expected 200 from download endpoint, got {response.status_code}. "
            f"Response: {response.text[:300]}"
        )

    @pytest.mark.asyncio
    async def test_provenance_call_records_are_non_empty(
        self, tmp_path: Path
    ) -> None:
        """Smoke-test provenance records have expected fields populated."""
        from api.artifact_service import generate as artifact_generate

        real_model = _best_langchain_model()

        with patch(
            "open_notebook.ai.provision.provision_langchain_model",
            new=AsyncMock(return_value=real_model),
        ):
            result = await artifact_generate(
                artifact_type="briefing",
                sources=[{"title": "Smoke", "content": _SMALL_CONTENT}],
                output_dir=str(tmp_path),
            )

        assert result.provenance is not None
        call = result.provenance.calls[0]
        assert call.latency_ms is not None and call.latency_ms >= 0
        assert call.prompt_hash and len(call.prompt_hash) >= 8


# ---------------------------------------------------------------------------
# Unit: command layer wiring (offline, no real LLM)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCommandLayerWiring:
    """Assert that the command module is wired to the queue correctly.

    These tests are offline: no SurrealDB, no real LLM, no file I/O.
    They confirm that submit_command is invoked when the router is called
    and that get_job_status correctly maps the queue status object.
    """

    def test_submit_generation_job_calls_submit_command(self) -> None:
        """POST /api/artifacts/generate must call submit_command."""
        import asyncio as _asyncio

        submitted_args: list = []
        fake_job_id = "command:abc-unit-test"

        def _fake_submit(app, command_name, args):
            submitted_args.append((app, command_name, args))
            return fake_job_id

        with patch("api.artifact_service.submit_command", side_effect=_fake_submit):
            from api.artifact_service import submit_generation_job

            loop = _asyncio.new_event_loop()
            try:
                job_id = loop.run_until_complete(
                    submit_generation_job(
                        artifact_type="briefing",
                        sources=[{"title": "T", "content": "C"}],
                    )
                )
            finally:
                loop.close()

        assert job_id == fake_job_id
        assert len(submitted_args) == 1
        app, cmd, args = submitted_args[0]
        assert app == "open_notebook"
        assert cmd == "generate_artifact"
        assert args["artifact_type"] == "briefing"

    def test_command_registered_with_correct_retry_config(self) -> None:
        """The generate_artifact command must be registered with max_attempts=5."""
        import commands.artifact_commands  # noqa: F401 — trigger registration

        from surreal_commands.core.registry import CommandRegistry

        registry = CommandRegistry()
        item = registry.get_command("open_notebook", "generate_artifact")
        assert item is not None, "generate_artifact not in registry"
        retry = item.retry_config
        assert retry is not None
        assert retry.max_attempts == 5, f"Expected max_attempts=5, got {retry.max_attempts}"
        from surreal_commands import RetryStrategy

        assert retry.wait_strategy == RetryStrategy.EXPONENTIAL_JITTER
        assert ValueError in (retry.stop_on or [])

    @pytest.mark.asyncio
    async def test_get_job_status_maps_completed(self) -> None:
        """get_job_status maps completed status correctly."""
        from api.artifact_service import get_job_status

        fake_result = MagicMock()
        fake_result.status = "completed"
        fake_result.result = {
            "artifact_type": "briefing",
            "title": "Test",
            "summary": "summary",
            "structured": {},
            "files": [{"path": "/tmp/x.md", "mime_type": "text/markdown", "description": ""}],
            "metadata": {},
            "provenance": None,
            "generated_at": "2026-04-22T00:00:00+00:00",
        }
        fake_result.error_message = None

        with patch(
            "api.artifact_service.get_command_status",
            new=AsyncMock(return_value=fake_result),
        ):
            status = await get_job_status("command:test-id")

        assert status["status"] == "completed"
        assert status["artifact_type"] == "briefing"
        assert status["files"][0]["path"] == "/tmp/x.md"

    @pytest.mark.asyncio
    async def test_get_job_status_maps_failed(self) -> None:
        """get_job_status preserves error_message for failed jobs."""
        from api.artifact_service import get_job_status

        fake_result = MagicMock()
        fake_result.status = "failed"
        fake_result.result = {}
        fake_result.error_message = "LLM provider timeout"

        with patch(
            "api.artifact_service.get_command_status",
            new=AsyncMock(return_value=fake_result),
        ):
            status = await get_job_status("command:test-id")

        assert status["status"] == "failed"
        assert status["error"] == "LLM provider timeout"

    def test_command_output_contains_provenance_field(self) -> None:
        """ArtifactGenerationOutput must have a provenance field."""
        from commands.artifact_commands import ArtifactGenerationOutput

        out = ArtifactGenerationOutput(
            success=False,
            artifact_type="briefing",
            error_message="test",
        )
        assert out.provenance is None

        out2 = ArtifactGenerationOutput(
            success=True,
            artifact_type="briefing",
            provenance={"run_id": "r1", "artifact_type": "briefing", "calls": []},
        )
        assert out2.provenance is not None

    def test_command_input_schema(self) -> None:
        """ArtifactGenerationInput must carry all required fields."""
        from commands.artifact_commands import ArtifactGenerationInput

        inp = ArtifactGenerationInput(
            artifact_type="briefing",
            sources=[{"title": "T", "content": "C"}],
        )
        assert inp.artifact_type == "briefing"
        assert len(inp.sources) == 1
        assert inp.notebook_id is None
        assert inp.model_id is None
