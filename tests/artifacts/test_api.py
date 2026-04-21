"""API surface tests for the artifacts router."""
from __future__ import annotations

import pytest

from api import artifact_service


@pytest.mark.asyncio
async def test_available_types_list():
    types = artifact_service.available_types()
    names = {t["type"] for t in types}
    assert "briefing" in names and "pitch_deck" in names


@pytest.mark.asyncio
async def test_generate_inline_sources(sample_sources, output_dir):
    result = await artifact_service.generate(
        artifact_type="faq",
        sources=[s.model_dump() for s in sample_sources],
        output_dir=output_dir,
    )
    assert result.artifact_type == "faq"


@pytest.mark.asyncio
async def test_generate_requires_any_source():
    with pytest.raises(ValueError):
        await artifact_service.generate(artifact_type="faq")


def test_router_imports():
    from api.routers import artifacts

    route_paths = {r.path for r in artifacts.router.routes}
    assert "/artifacts/generate" in route_paths
    assert "/artifacts/types" in route_paths
    assert "/artifacts/download" in route_paths
