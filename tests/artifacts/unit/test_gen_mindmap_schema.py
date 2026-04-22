"""Unit tests for MindMapGenerator — schema, registry, and model-type checks.

No real LLM calls. Tests verify:
1. MindMapSchema / MindMapBranchSchema have required fields.
2. MindMapGenerator is registered in ARTIFACT_TYPES.
3. MindMapGenerator.default_model_type is set.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_mindmap_schema_required_fields() -> None:
    """MindMapSchema must expose central_topic and branches."""
    from open_notebook.artifacts.generators.mindmap import MindMapSchema

    schema_fields = set(MindMapSchema.model_fields.keys())
    required = {"central_topic", "branches"}
    missing = required - schema_fields
    assert not missing, (
        f"MindMapSchema is missing required fields: {missing}. Present: {schema_fields}"
    )


def test_mindmap_branch_schema_required_fields() -> None:
    """MindMapBranchSchema must have label and children."""
    from open_notebook.artifacts.generators.mindmap import MindMapBranchSchema

    branch_fields = set(MindMapBranchSchema.model_fields.keys())
    required = {"label", "children"}
    missing = required - branch_fields
    assert not missing, (
        f"MindMapBranchSchema is missing required fields: {missing}. Present: {branch_fields}"
    )


def test_mindmap_schema_instantiation() -> None:
    """MindMapSchema must be constructible with valid nested data."""
    from open_notebook.artifacts.generators.mindmap import MindMapBranchSchema, MindMapSchema

    obj = MindMapSchema(
        central_topic="Attention Mechanism",
        branches=[
            MindMapBranchSchema(
                label="Query-Key-Value",
                children=["Dot product similarity", "Softmax normalisation", "Weighted values"],
            ),
            MindMapBranchSchema(
                label="Multi-Head Attention",
                children=["Parallel heads", "Concatenated output", "Linear projection"],
            ),
        ],
    )
    assert obj.central_topic == "Attention Mechanism"
    assert len(obj.branches) == 2
    dumped = obj.model_dump()
    assert dumped["branches"][0]["label"] == "Query-Key-Value"
    assert len(dumped["branches"][0]["children"]) == 3


def test_mindmap_generator_in_registry() -> None:
    """MindMapGenerator must be registered in ARTIFACT_TYPES."""
    from open_notebook.artifacts.registry import ARTIFACT_TYPES

    assert "mindmap" in ARTIFACT_TYPES, (
        f"'mindmap' not in ARTIFACT_TYPES. Registered: {sorted(ARTIFACT_TYPES.keys())}"
    )


def test_mindmap_generator_default_model_type() -> None:
    """MindMapGenerator.default_model_type must be a non-empty string."""
    from open_notebook.artifacts.generators.mindmap import MindMapGenerator

    assert MindMapGenerator.default_model_type, (
        "MindMapGenerator.default_model_type must be set."
    )
    assert isinstance(MindMapGenerator.default_model_type, str)


def test_mindmap_generator_uses_chunked_generate() -> None:
    """MindMapGenerator.generate must call chunked_generate."""
    import inspect

    from open_notebook.artifacts.generators.mindmap import MindMapGenerator

    source = inspect.getsource(MindMapGenerator.generate)
    assert "chunked_generate" in source, (
        "MindMapGenerator.generate must call self.chunked_generate()."
    )
    assert "generate_json" not in source, (
        "MindMapGenerator must not use generate_json (legacy)."
    )
