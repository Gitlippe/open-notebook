"""End-to-end generator tests. Runs every generator in heuristic mode and
with a canned LLM fixture; validates file outputs, structure, and metadata.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from open_notebook.artifacts import generate_artifact
from open_notebook.artifacts.registry import get_generator


GENERATORS_EXPECTING_BINARY_FIRST = {
    "timeline": "image/png",
    "infographic": "image/png",
    "slide_deck": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "pitch_deck": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "paper_figure": "image/png",
}


def _minimum_file_size(mime: str) -> int:
    if mime == "image/png":
        return 300  # PNG header + at least some data
    if "presentationml" in mime:
        return 4000  # Empty pptx is still a zip with ~5KB
    if "wordprocessingml" in mime:
        return 3000
    return 10


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "artifact_type",
    [
        "briefing",
        "study_guide",
        "faq",
        "research_review",
        "flashcards",
        "quiz",
        "mindmap",
        "timeline",
        "infographic",
        "slide_deck",
        "pitch_deck",
        "paper_figure",
    ],
)
async def test_generator_runs_with_heuristic(
    artifact_type, sample_sources, output_dir
):
    result = await generate_artifact(
        artifact_type,
        sample_sources,
        output_dir=output_dir,
    )
    assert result.artifact_type == artifact_type
    assert result.title
    assert result.structured
    assert result.files, f"{artifact_type} produced no files"
    for f in result.files:
        p = Path(f.path)
        assert p.exists(), f"{artifact_type} file missing: {p}"
        assert p.stat().st_size > _minimum_file_size(f.mime_type), (
            f"{artifact_type} file {p} looks too small ({p.stat().st_size} bytes)"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "artifact_type",
    [
        "briefing",
        "study_guide",
        "faq",
        "research_review",
        "flashcards",
        "quiz",
        "mindmap",
        "timeline",
        "infographic",
        "slide_deck",
        "pitch_deck",
        "paper_figure",
    ],
)
async def test_generator_with_canned_llm(
    artifact_type, sample_sources, output_dir, canned_llm
):
    result = await generate_artifact(
        artifact_type,
        sample_sources,
        output_dir=output_dir,
        llm=canned_llm,
    )
    assert result.artifact_type == artifact_type
    assert result.files
    if artifact_type in GENERATORS_EXPECTING_BINARY_FIRST:
        expected = GENERATORS_EXPECTING_BINARY_FIRST[artifact_type]
        mimes = [f.mime_type for f in result.files]
        assert expected in mimes, f"Expected {expected} in {mimes}"


@pytest.mark.asyncio
async def test_briefing_produces_docx(sample_sources, output_dir, canned_llm):
    result = await generate_artifact(
        "briefing", sample_sources, output_dir=output_dir, llm=canned_llm
    )
    mimes = [f.mime_type for f in result.files]
    assert any("wordprocessingml" in m for m in mimes)
    assert result.structured.get("bluf") == "A fixture BLUF."


@pytest.mark.asyncio
async def test_flashcards_produces_apkg(sample_sources, output_dir, canned_llm):
    result = await generate_artifact(
        "flashcards", sample_sources, output_dir=output_dir, llm=canned_llm
    )
    apkg_files = [f for f in result.files if f.path.endswith(".apkg")]
    assert apkg_files, "Expected at least one .apkg file"
    p = Path(apkg_files[0].path)
    data = p.read_bytes()
    assert data[:4] == b"PK\x03\x04", "APKG should be a zip file"


@pytest.mark.asyncio
async def test_mindmap_mermaid_and_dot(sample_sources, output_dir, canned_llm):
    result = await generate_artifact(
        "mindmap", sample_sources, output_dir=output_dir, llm=canned_llm
    )
    paths = {Path(f.path).suffix: f.path for f in result.files}
    assert ".mmd" in paths
    assert ".dot" in paths
    mermaid = Path(paths[".mmd"]).read_text()
    assert mermaid.startswith("mindmap")
    dot = Path(paths[".dot"]).read_text()
    assert "digraph mindmap" in dot


@pytest.mark.asyncio
async def test_quiz_answer_index_in_range(sample_sources, output_dir, canned_llm):
    result = await generate_artifact(
        "quiz", sample_sources, output_dir=output_dir, llm=canned_llm
    )
    for q in result.structured["questions"]:
        assert 0 <= q["answer_index"] < len(q["options"])


@pytest.mark.asyncio
async def test_slide_deck_structure(sample_sources, output_dir, canned_llm):
    result = await generate_artifact(
        "slide_deck", sample_sources, output_dir=output_dir, llm=canned_llm
    )
    pptx = next(f for f in result.files if f.path.endswith(".pptx"))
    assert Path(pptx.path).stat().st_size > 4000


@pytest.mark.asyncio
async def test_timeline_renders_png(sample_sources, output_dir, canned_llm):
    result = await generate_artifact(
        "timeline", sample_sources, output_dir=output_dir, llm=canned_llm
    )
    png = next(f for f in result.files if f.path.endswith(".png"))
    header = Path(png.path).read_bytes()[:8]
    assert header.startswith(b"\x89PNG"), "Timeline PNG header invalid"


@pytest.mark.asyncio
async def test_paper_figure_bar(sample_sources, output_dir, canned_llm):
    result = await generate_artifact(
        "paper_figure",
        sample_sources,
        output_dir=output_dir,
        llm=canned_llm,
        config={"chart_type": "bar"},
    )
    png = next(f for f in result.files if f.path.endswith(".png"))
    header = Path(png.path).read_bytes()[:8]
    assert header.startswith(b"\x89PNG")


@pytest.mark.asyncio
async def test_infographic_png_and_html(sample_sources, output_dir, canned_llm):
    result = await generate_artifact(
        "infographic", sample_sources, output_dir=output_dir, llm=canned_llm
    )
    paths = {Path(f.path).suffix: f.path for f in result.files}
    assert ".png" in paths and ".html" in paths
    html = Path(paths[".html"]).read_text()
    assert "Generated by Open Notebook" in html


@pytest.mark.asyncio
async def test_json_structured_matches_written_file(
    sample_sources, output_dir, canned_llm
):
    result = await generate_artifact(
        "study_guide", sample_sources, output_dir=output_dir, llm=canned_llm
    )
    json_file = next(f for f in result.files if f.path.endswith(".json"))
    written = json.loads(Path(json_file.path).read_text())
    assert written.get("title") == result.structured.get("title")


@pytest.mark.asyncio
async def test_fingerprint_stable_for_same_input(
    sample_sources, output_dir, canned_llm
):
    r1 = await generate_artifact(
        "faq", sample_sources, output_dir=output_dir, llm=canned_llm
    )
    r2 = await generate_artifact(
        "faq", sample_sources, output_dir=output_dir, llm=canned_llm
    )
    names1 = {Path(f.path).name for f in r1.files}
    names2 = {Path(f.path).name for f in r2.files}
    assert names1 == names2


@pytest.mark.asyncio
async def test_registry_get_generator_instantiates(sample_sources, output_dir):
    gen = get_generator("briefing")
    from open_notebook.artifacts.base import ArtifactRequest

    req = ArtifactRequest(
        artifact_type="briefing", sources=sample_sources, output_dir=output_dir
    )
    result = await gen.generate(req)
    assert result.artifact_type == "briefing"
