# Artifact Generation

Open Notebook ships with a comprehensive artifact-generation suite that
turns research sources into finished deliverables. In addition to the
existing podcast generator, the following artifact types are available:

| Artifact | Outputs |
|---|---|
| `briefing` | BLUF executive memo (Markdown + DOCX + JSON) |
| `study_guide` | Structured study guide (Markdown + DOCX + JSON) |
| `faq` | Frequently asked questions (Markdown + JSON) |
| `research_review` | Skeptical peer review (Markdown + JSON) |
| `flashcards` | Anki `.apkg` deck + JSON |
| `quiz` | Multiple-choice quiz (Markdown + JSON) |
| `mindmap` | Mermaid + Graphviz DOT + optional PNG + Markdown outline |
| `timeline` | Chronological chart (PNG + Markdown + JSON) |
| `infographic` | Single-page infographic (PNG + HTML + JSON) |
| `slide_deck` | Informational deck (`.pptx` + Markdown + JSON) |
| `pitch_deck` | Venture-style deck (`.pptx` + Markdown + JSON) |
| `paper_figure` | Publication figure (PNG + JSON) |

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│ Sources / Notebook Context                              │
└────────────────────┬─────────────────────────────────────┘
                     ▼
┌──────────────────────────────────────────────────────────┐
│ Artifact Generator (one per artifact type)              │
│                                                          │
│  ArtifactRequest → LLM prompt → ArtifactLLM.generate    │
│                         │                                │
│                         ▼                                │
│          ┌────────────────────────────┐                  │
│          │ provision_langchain_model  │ (online LLM)     │
│          │ OR deterministic heuristic │ (offline)        │
│          └────────────────────────────┘                  │
│                         │                                │
│                         ▼ structured JSON                │
│          ┌────────────────────────────┐                  │
│          │ Renderer (format-specific) │                  │
│          └────────────────────────────┘                  │
└────────────────────┬─────────────────────────────────────┘
                     ▼
           ArtifactResult → files on disk
```

Every generator ultimately emits an `ArtifactResult` with:

- `structured` — the structured JSON payload used to render the artifact
- `files` — a list of `ArtifactFile` entries pointing at generated files
- `summary` / `title` / `metadata` for display

### Offline-ready by design

`ArtifactLLM` tries `provision_langchain_model` only when `ARTIFACT_USE_LLM=1`
and a provider key is configured. Otherwise, every artifact still works
end-to-end thanks to a deterministic heuristic extractor built into
`open_notebook.artifacts.heuristic`. This means:

- Unit tests and CI never need API keys
- Local demos work immediately
- First-time users can explore every feature before configuring AI

When an LLM is available, the same pipeline seamlessly uses it for
significantly higher-quality output.

## Python API

```python
from open_notebook.artifacts import generate_artifact

result = await generate_artifact(
    artifact_type="research_review",
    sources=[
        {"title": "Paper", "content": "..."},
    ],
    config={"tone": "skeptical"},
    output_dir="/tmp/artifacts",
)
print(result.primary_file().path)
```

## REST API

```
GET  /api/artifacts/types         # List available artifact types
POST /api/artifacts/generate      # Generate an artifact synchronously
GET  /api/artifacts/download?path=... # Stream a generated file
```

Long-running generations can be submitted as background jobs via the
existing `/api/commands/...` flow. The matching command name is
`open_notebook.generate_artifact`.

## Demos

See `demos/` for end-to-end agent scripts, one per artifact type plus a
multi-artifact integration demo. Run all of them with:

```bash
uv run python demos/run_all_demos.py
```

Outputs land under `demos/_output/<demo_name>/`.

## Adding a new artifact type

1. Create `open_notebook/artifacts/generators/<name>.py`
2. Subclass `BaseArtifactGenerator`, set `artifact_type = "<name>"`, decorate with `@register_generator`
3. Define a prompt in `open_notebook/artifacts/prompts.py`
4. Reuse or add a renderer in `open_notebook/artifacts/renderers/`
5. Optionally extend `open_notebook/artifacts/heuristic.py` with an
   offline fallback keyed by the artifact type
6. Add tests under `tests/artifacts/`
7. Add a demo in `demos/`
