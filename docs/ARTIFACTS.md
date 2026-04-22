# Artifact Generation

Open Notebook generates twelve structured artifact types from research
sources alongside the existing podcast generator. Every artifact runs
through a multi-step pipeline with schema-constrained LLM output,
self-critique, and refinement.

| Artifact | Outputs |
|---|---|
| `briefing` | BLUF executive memo (Markdown + DOCX + JSON) |
| `study_guide` | Bloom-taxonomy-aware guide (Markdown + DOCX + JSON) |
| `faq` | FAQ (Markdown + JSON) |
| `research_review` | Skeptical review with verdict + confidence (Markdown + JSON) |
| `flashcards` | Anki `.apkg` with multi-Bloom cards (+ JSON) |
| `quiz` | MCQ quiz with Bloom × difficulty matrix (Markdown + JSON) |
| `mindmap` | Mermaid + Graphviz DOT + optional PNG + Markdown outline |
| `timeline` | Chronological PNG + Markdown + JSON |
| `infographic` | Single-page PNG + HTML + JSON with lede / stats / takeaway banner |
| `slide_deck` | Narrative-arc planned `.pptx` (6+ typed layouts) |
| `pitch_deck` | Canonical VC arc `.pptx` |
| `paper_figure` | Publication-grade matplotlib PNG with highlight series + caption |

## Pipeline

Every generator runs the same four-phase pipeline:

```
┌────────────────────────────────────────────────────┐
│ 1. Claim extraction                                │
│    Structured output: ClaimSet Pydantic schema     │
│    - atomic claims with evidence + importance      │
│    - numeric facts                                 │
│    - named entities                                │
└─────────────────────┬──────────────────────────────┘
                      ▼
┌────────────────────────────────────────────────────┐
│ 2. Structured draft                                │
│    Structured output: artifact-specific schema     │
│    - strict typing (Literal, Field constraints)    │
│    - max/min list lengths enforced                 │
│    - @model_validator invariants                   │
└─────────────────────┬──────────────────────────────┘
                      ▼
┌────────────────────────────────────────────────────┐
│ 3. Self-critique                                   │
│    Structured output: Critique schema              │
│    - issues, missing facts, redundancies           │
│    - suggested_edits, quality_score 1-10           │
└─────────────────────┬──────────────────────────────┘
                      ▼
┌────────────────────────────────────────────────────┐
│ 4. Refinement (up to `max_passes`)                 │
│    Same structured output as the draft phase       │
│    Stops when quality_score >= `quality_floor`     │
│    AND no issues remain.                           │
└─────────────────────┬──────────────────────────────┘
                      ▼
              Renderer (format-specific)
```

## LLM backends

`ArtifactLLM` exposes a single protocol:

```python
async def structured(system_prompt, user_prompt, schema, temperature) -> T
async def text(system_prompt, user_prompt, temperature) -> str
```

Two backends implement it:

1. **`LangChainChat`** — wraps `provision_langchain_model` when SurrealDB
   is available, or falls back to `init_chat_model` keyed off the first
   provider env var present (OPENAI, ANTHROPIC, GROQ, Gemini, Mistral,
   DeepSeek, xAI, OpenRouter). Uses LangChain's
   `.with_structured_output(schema)` so the return value is a validated
   Pydantic object.
2. **`StructuredMockChat`** — the offline backend used automatically when
   no provider is configured. It implements the identical protocol and
   returns real, schema-valid Pydantic instances composed from extractive
   analysis of the source material. **It does not bypass the pipeline** —
   the claim-extraction / critique / refinement phases all run against
   the mock the same way they run against the real LLM.

No environment flag gates this. If a provider key is set, the real LLM is
used. Otherwise the mock runs. Tests always use the mock; production runs
always use the real LLM.

## Python API

```python
from open_notebook.artifacts import generate_artifact

result = await generate_artifact(
    artifact_type="research_review",
    sources=[{"title": "Paper", "content": "..."}],
    config={"tone": "brutally honest"},
    output_dir="/tmp/artifacts",
)
print(result.structured["verdict"])   # 'adopt' | 'pilot' | 'watch' | 'skip'
print(result.structured["confidence"])  # 'high' | 'medium' | 'low'
print(result.primary_file().path)
```

## REST API

```
GET  /api/artifacts/types         # List available artifact types
POST /api/artifacts/generate      # Generate an artifact synchronously
GET  /api/artifacts/download?path=... # Stream a generated file
```

Long-running jobs submit to `surreal-commands` via
`open_notebook.generate_artifact`; poll `/api/commands/{id}` for status.

## Schemas

Every artifact has a strict Pydantic schema under
`open_notebook.artifacts.schemas`:

- Field-level constraints (`min_length`, `max_length`, `ge`, `le`)
- `Literal` types for enumerated fields (e.g. `verdict`, `bloom_level`)
- `@model_validator` invariants (flashcards span ≥3 Bloom levels, quiz
  answer_index in range)

Schemas serve three purposes:

- Prompt spec — `.with_structured_output(schema)` surfaces field doctrings
  to the LLM
- Runtime validation — invalid outputs raise at the boundary, not silently
- Rendering contract — renderers consume the validated object directly

## Adding a new artifact type

1. Add the schema class in `open_notebook/artifacts/schemas.py`
2. Add a composer to `StructuredMockChat` for offline support
3. Create `open_notebook/artifacts/generators/<name>.py` subclassing
   `BaseArtifactGenerator`, decorate with `@register_generator`, call
   `extract_claims` → `claims_to_context` → `draft_and_refine` → renderer
4. Reuse or add a renderer in `open_notebook/artifacts/renderers/`
5. Write tests under `tests/artifacts/`
6. Add a demo in `demos/`

## Demos

See `demos/` for one agent script per artifact type plus a multi-artifact
integration demo. Run all of them with:

```bash
PYTHONPATH=. uv run python demos/run_all_demos.py
```
