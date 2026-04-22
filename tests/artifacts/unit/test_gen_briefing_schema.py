"""Unit tests for BriefingGenerator — schema, registry, and model-type checks.

No real LLM calls. Tests verify:
1. BriefingSchema has all required fields.
2. BriefingGenerator is registered in ARTIFACT_TYPES.
3. BriefingGenerator.default_model_type is set.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_briefing_schema_required_fields() -> None:
    """BriefingSchema must expose the BLUF fields the plan requires."""
    from open_notebook.artifacts.generators.briefing import BriefingSchema

    schema_fields = set(BriefingSchema.model_fields.keys())
    required = {"title", "audience", "bluf", "key_points", "action_items"}
    missing = required - schema_fields
    assert not missing, (
        f"BriefingSchema is missing required fields: {missing}. "
        f"Present: {schema_fields}"
    )


def test_briefing_schema_instantiation() -> None:
    """BriefingSchema must be constructible with valid data."""
    from open_notebook.artifacts.generators.briefing import BriefingSchema

    obj = BriefingSchema(
        title="Test Briefing",
        audience="Engineering leadership",
        bluf="The single most important thing.",
        key_points=["Point A", "Point B", "Point C"],
        supporting_details=["Detail A"],
        action_items=["Do X immediately", "Schedule Y"],
        keywords=["ai", "ml"],
    )
    assert obj.bluf == "The single most important thing."
    assert len(obj.key_points) == 3
    dumped = obj.model_dump()
    assert isinstance(dumped["key_points"], list)


def test_briefing_generator_in_registry() -> None:
    """BriefingGenerator must be registered in ARTIFACT_TYPES."""
    # Importing registry triggers _autoregister()
    from open_notebook.artifacts.registry import ARTIFACT_TYPES

    assert "briefing" in ARTIFACT_TYPES, (
        f"'briefing' not found in ARTIFACT_TYPES. "
        f"Registered types: {sorted(ARTIFACT_TYPES.keys())}"
    )


def test_briefing_generator_default_model_type() -> None:
    """BriefingGenerator.default_model_type must be a non-empty string."""
    from open_notebook.artifacts.generators.briefing import BriefingGenerator

    assert BriefingGenerator.default_model_type, (
        "BriefingGenerator.default_model_type must be set to a non-empty string "
        "(e.g. 'transformation') so provision_langchain_model selects the right pool."
    )
    assert isinstance(BriefingGenerator.default_model_type, str)


def test_briefing_generator_uses_chunked_generate() -> None:
    """BriefingGenerator.generate must call chunked_generate (not generate_json)."""
    import inspect

    from open_notebook.artifacts.generators.briefing import BriefingGenerator

    source = inspect.getsource(BriefingGenerator.generate)
    assert "chunked_generate" in source, (
        "BriefingGenerator.generate must call self.chunked_generate(). "
        "Using generate_json or generate_text directly bypasses map-reduce "
        "for long inputs."
    )
    assert "generate_json" not in source, (
        "BriefingGenerator.generate must not call generate_json (legacy API). "
        "Use chunked_generate with schema=BriefingSchema instead."
    )


def test_briefing_result_includes_provenance() -> None:
    """ArtifactResult from BriefingGenerator must attach provenance."""
    # We do NOT make a real LLM call; we verify the code path sets provenance.
    import inspect

    from open_notebook.artifacts.generators.briefing import BriefingGenerator

    source = inspect.getsource(BriefingGenerator.generate)
    assert "self.llm.provenance" in source, (
        "BriefingGenerator.generate must set provenance=self.llm.provenance "
        "on ArtifactResult so integration tests can prove real LLM usage."
    )
