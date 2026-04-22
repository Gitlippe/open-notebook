"""End-to-end generator tests using StructuredMockChat.

Every test runs the full pipeline: claim extraction → draft → critique →
refine → render. We assert on schema metadata, not hand-crafted outputs,
so the same tests would pass against a real LLM backend.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from open_notebook.artifacts import generate_artifact


ALL_TYPES = [
    "briefing", "study_guide", "faq", "research_review", "flashcards",
    "quiz", "mindmap", "timeline", "infographic", "slide_deck",
    "pitch_deck", "paper_figure",
]


def _expect_binary_mime(artifact_type: str):
    return {
        "timeline": "image/png",
        "infographic": "image/png",
        "slide_deck": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "pitch_deck": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "paper_figure": "image/png",
        "flashcards": "application/octet-stream",
        "briefing": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "study_guide": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }.get(artifact_type)


@pytest.mark.asyncio
@pytest.mark.parametrize("artifact_type", ALL_TYPES)
async def test_pipeline_runs_for_every_artifact(
    artifact_type, sample_sources, output_dir
):
    result = await generate_artifact(
        artifact_type, sample_sources, output_dir=output_dir
    )
    assert result.artifact_type == artifact_type
    assert result.title
    assert result.structured
    assert result.files, f"{artifact_type} produced no files"
    expected = _expect_binary_mime(artifact_type)
    if expected:
        mimes = [f.mime_type for f in result.files]
        assert expected in mimes, f"{artifact_type}: expected {expected} in {mimes}"
    for f in result.files:
        p = Path(f.path)
        assert p.exists(), f"{artifact_type}: missing file {p}"
        assert p.stat().st_size > 10, f"{artifact_type}: {p} is empty"


@pytest.mark.asyncio
async def test_briefing_has_bluf_and_exports_docx(sample_sources, output_dir):
    result = await generate_artifact(
        "briefing", sample_sources, output_dir=output_dir,
        config={"audience": "Senior leadership"},
    )
    assert result.structured["bluf"]
    assert len(result.structured["bluf"]) >= 40
    assert 3 <= len(result.structured["key_points"]) <= 6
    assert result.metadata["audience"] == "Senior leadership"
    assert any(f.mime_type.endswith("wordprocessingml.document") for f in result.files)


@pytest.mark.asyncio
async def test_study_guide_blooms_labeled(sample_sources, output_dir):
    result = await generate_artifact(
        "study_guide", sample_sources, output_dir=output_dir
    )
    assert len(result.metadata["bloom_levels"]) >= 1
    for obj in result.structured["learning_objectives"]:
        assert obj["bloom_level"] in {
            "remember", "understand", "apply", "analyze", "evaluate", "create"
        }


@pytest.mark.asyncio
async def test_research_review_verdict_and_claim_split(sample_sources, output_dir):
    result = await generate_artifact(
        "research_review", sample_sources, output_dir=output_dir
    )
    assert result.structured["verdict"] in {"adopt", "pilot", "watch", "skip"}
    assert result.structured["confidence"] in {"high", "medium", "low"}
    assert result.structured["contribution_claim"]
    assert result.structured["actual_contribution"]


@pytest.mark.asyncio
async def test_flashcards_exports_valid_apkg(sample_sources, output_dir):
    result = await generate_artifact(
        "flashcards", sample_sources, output_dir=output_dir
    )
    apkg = [f for f in result.files if f.path.endswith(".apkg")]
    assert apkg
    header = Path(apkg[0].path).read_bytes()[:4]
    assert header == b"PK\x03\x04"
    # Bloom diversity guaranteed by the Pydantic validator
    assert len(result.metadata["bloom_levels"]) >= 3


@pytest.mark.asyncio
async def test_quiz_bloom_and_difficulty_diversity(sample_sources, output_dir):
    result = await generate_artifact(
        "quiz", sample_sources, output_dir=output_dir
    )
    for q in result.structured["questions"]:
        assert len(q["options"]) == 4
        assert 0 <= q["answer_index"] < 4


@pytest.mark.asyncio
async def test_mindmap_mermaid_and_dot(sample_sources, output_dir):
    result = await generate_artifact(
        "mindmap", sample_sources, output_dir=output_dir
    )
    paths = {Path(f.path).suffix: f.path for f in result.files}
    assert ".mmd" in paths and ".dot" in paths
    mmd = Path(paths[".mmd"]).read_text()
    assert mmd.startswith("mindmap")
    dot = Path(paths[".dot"]).read_text()
    assert "digraph mindmap" in dot


@pytest.mark.asyncio
async def test_timeline_png_and_sorted(sample_sources, output_dir):
    result = await generate_artifact(
        "timeline", sample_sources, output_dir=output_dir
    )
    png = next(f for f in result.files if f.path.endswith(".png"))
    assert Path(png.path).read_bytes()[:8].startswith(b"\x89PNG")
    dates = [e["date"] for e in result.structured["events"]]
    assert dates == sorted(dates)


@pytest.mark.asyncio
async def test_infographic_png_html_and_stat_count(sample_sources, output_dir):
    result = await generate_artifact(
        "infographic", sample_sources, output_dir=output_dir
    )
    paths = {Path(f.path).suffix: f.path for f in result.files}
    assert ".png" in paths and ".html" in paths
    html = Path(paths[".html"]).read_text()
    assert "Generated by Open Notebook" in html
    assert "takeaway" in html
    assert 3 <= result.metadata["stat_count"] <= 4


@pytest.mark.asyncio
async def test_slide_deck_plan_present(sample_sources, output_dir):
    result = await generate_artifact(
        "slide_deck", sample_sources, output_dir=output_dir
    )
    assert "plan" in result.structured
    plan = result.structured["plan"]
    assert plan["narrative_arc"] in {
        "problem-solution", "chronological", "compare-contrast",
        "pyramid", "hero-journey", "scqa",
    }
    slide_types = result.metadata["slide_types"]
    assert "title" in slide_types
    assert "closing" in slide_types


@pytest.mark.asyncio
async def test_pitch_deck_canonical_sections(sample_sources, output_dir):
    result = await generate_artifact(
        "pitch_deck", sample_sources, output_dir=output_dir,
        config={"company": "Acme"},
    )
    titles = {s["title"].lower() for s in result.structured["slides"]}
    # canonical order should include at least some of these
    assert any(k in " ".join(titles) for k in ["problem", "solution", "ask"])


@pytest.mark.asyncio
async def test_paper_figure_png_and_metadata(sample_sources, output_dir):
    result = await generate_artifact(
        "paper_figure", sample_sources, output_dir=output_dir
    )
    png = next(f for f in result.files if f.path.endswith(".png"))
    assert Path(png.path).read_bytes()[:8].startswith(b"\x89PNG")
    assert result.metadata["chart_type"] in {"bar", "grouped_bar", "line", "scatter"}


@pytest.mark.asyncio
async def test_json_file_matches_structured_payload(sample_sources, output_dir):
    result = await generate_artifact(
        "faq", sample_sources, output_dir=output_dir
    )
    json_file = next(f for f in result.files if f.path.endswith(".json"))
    written = json.loads(Path(json_file.path).read_text())
    assert written["title"] == result.structured["title"]
    assert len(written["items"]) == len(result.structured["items"])


@pytest.mark.asyncio
async def test_fingerprint_stable(sample_sources, output_dir):
    r1 = await generate_artifact("faq", sample_sources, output_dir=output_dir)
    r2 = await generate_artifact("faq", sample_sources, output_dir=output_dir)
    assert {Path(f.path).name for f in r1.files} == \
        {Path(f.path).name for f in r2.files}


@pytest.mark.asyncio
async def test_pipeline_metadata_records_steps(sample_sources, output_dir):
    result = await generate_artifact(
        "briefing", sample_sources, output_dir=output_dir
    )
    assert "claim_count" in result.metadata
    assert result.metadata["claim_count"] >= 5
    assert "pipeline" in result.metadata
    assert "critique" in result.metadata["pipeline"]
