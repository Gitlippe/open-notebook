# Artifact Generation Report
## Open Notebook — Capability Assessment & External Module Catalogue

---

## Executive Summary

Google NotebookLM generates **twelve distinct artifact types** from research materials. Open Notebook — which explicitly positions itself as the open-source counterpart — fully implements **exactly one** of them: the **Audio Overview (Podcast)**. Every other artifact type is absent from the codebase.

The gap is not architectural. Open Notebook's infrastructure — LangGraph workflow orchestration, the Esperanto multi-provider AI abstraction, the `ContextBuilder` RAG assembly layer, the `surreal-commands` background job queue, and Jinja2-based prompt templating — constitutes a near-perfect scaffold for implementing any of the missing artifact types. The podcast module itself serves as a ready-made blueprint that can be cloned and adapted.

The external Python ecosystem provides mature, well-maintained, and LangChain/LangGraph-compatible libraries for every missing artifact type. None require significant architectural changes to the host application.

**The single most important finding:** a `presentation-creator` library analogous to the existing `podcast-creator` does not yet exist in the `lfnovo` ecosystem. This represents the clearest opportunity — and the clearest gap.

---

## Table of Contents

1. [NotebookLM Artifact Taxonomy](#1-notebooklm-artifact-taxonomy)
2. [Open Notebook Architecture — What Already Works](#2-open-notebook-architecture--what-already-works)
3. [Module-by-Module Gap Analysis](#3-module-by-module-gap-analysis)
   - 3.1 [Presentation / Slide Deck Generation](#31-presentation--slide-deck-generation)
   - 3.2 [Infographic Generation](#32-infographic-generation)
   - 3.3 [Mind Map Generation](#33-mind-map-generation)
   - 3.4 [Timeline Generation](#34-timeline-generation)
   - 3.5 [Flashcard Generation](#35-flashcard-generation)
   - 3.6 [Quiz Generation](#36-quiz-generation)
   - 3.7 [Study Guide & Briefing Document Generation](#37-study-guide--briefing-document-generation)
4. [The Podcast Module as the Implementation Blueprint](#4-the-podcast-module-as-the-implementation-blueprint)
5. [Extraction Viability Assessment](#5-extraction-viability-assessment)
6. [Recommended Implementation Roadmap](#6-recommended-implementation-roadmap)
7. [Complete External Module Catalogue](#7-complete-external-module-catalogue)

---

## 1. NotebookLM Artifact Taxonomy

NotebookLM produces artifacts across three broad categories. The table below maps each artifact to its Open Notebook status.

| # | Artifact Type | NotebookLM Description | Open Notebook Status |
|---|---|---|---|
| 1 | **Audio Overview (Podcast)** | Two AI hosts discuss and analyse sources; interactive; multi-format | ✅ **Fully Implemented** |
| 2 | **Slide Deck / Presentation** | Professional slides (Presenter or Detailed format); visual AI-powered | ❌ Not present |
| 3 | **Infographic** | Single-page visual summary; key stats, colour themes, layout styles | ❌ Not present |
| 4 | **Mind Map** | Interactive branching diagram of topics and relationships | ❌ Not present |
| 5 | **Study Guide** | Key concepts, glossary, essay prompts, exam prep | ❌ Not present |
| 6 | **Briefing Document** | Executive summary / structured synthesis of sources | ❌ Not present |
| 7 | **FAQ** | Auto-generated Q&A derived from source documents | ❌ Not present |
| 8 | **Timeline** | Chronological visual extraction of events from sources | ❌ Not present |
| 9 | **Flashcards** | Q&A pairs for study, difficulty-configurable | ❌ Not present |
| 10 | **Quiz** | MCQ assessments generated from sources | ❌ Not present |
| 11 | **Video Overview** | Narrated video with visual styles (whiteboard, anime, etc.) | ❌ Not present |
| 12 | **Data Table** | Structured tabular extraction from sources | ❌ Not present |

**Sources:**
- https://support.google.com/notebooklm/answer/16758265
- https://www.leadwithai.co/article/create-slide-decks-and-infographics-with-notebooklm
- https://blog.google/innovation-and-ai/models-and-research/google-labs/8-ways-to-make-the-most-out-of-slide-decks-in-notebooklm/

---

## 2. Open Notebook Architecture — What Already Works

Before assessing gaps, it is critical to understand what the existing architecture already provides, because it makes almost every missing artifact trivially addable at the orchestration level.

### 2.1 LangGraph Workflow Engine (`open_notebook/graphs/`)

Every artifact generator in Open Notebook is modelled as a `StateGraph`. The transformation graph is the minimal example:

```python
# open_notebook/graphs/transformation.py (lines 16–74)
class TransformationState(TypedDict):
    input_text: str
    source: Source
    transformation: Transformation
    output: str

agent_state = StateGraph(TransformationState)
agent_state.add_node("agent", run_transformation)
agent_state.add_edge(START, "agent")
agent_state.add_edge("agent", END)
graph = agent_state.compile()
```

Any new artifact (e.g., slides) can follow this exact pattern with a multi-node graph: `plan → generate_structure → render_artifact`.

### 2.2 Multi-Provider AI via Esperanto (`open_notebook/ai/provision.py`)

```python
# open_notebook/ai/provision.py (lines 10–17)
async def provision_langchain_model(
    content, model_id, default_type, **kwargs
) -> BaseChatModel:
    """
    Returns the best model based on context size and configuration.
    If context > 105,000 tokens → uses large_context_model
    If model_id specified → uses that model
    Otherwise → uses the default for the given type
    """
```

Any new graph node calls `provision_langchain_model(content, model_id, "artifact_type")` and automatically gets the right model from any of the 8+ supported providers (OpenAI, Anthropic, Google, Groq, Ollama, Mistral, DeepSeek, xAI).

### 2.3 RAG Context Assembly (`open_notebook/utils/context_builder.py`)

The `ContextBuilder` class (494 lines) assembles token-aware context from sources, notes, and insights. It is fully decoupled from any specific artifact type and can feed any new generator:

```python
# open_notebook/utils/context_builder.py (lines 105–136)
async def build(self) -> Dict[str, Any]:
    """Returns: {"sources": [...], "notes": [...], "insights": [...], "total_tokens": N}"""
```

### 2.4 Background Job Queue (`surreal-commands` + `api/podcast_service.py`)

Long-running generation jobs are submitted via `submit_command()` and polled via the `/commands/{id}` endpoint. This pattern is already live for podcast generation and requires zero modification to support any new artifact type:

```python
# api/podcast_service.py (line 96)
job_id = submit_command("open_notebook", "generate_podcast", command_args)
```

### 2.5 Jinja2 Prompt Templates (`prompts/`)

The `ai-prompter` library (a `lfnovo` project) renders Jinja2 templates from `prompts/`. Adding a new artifact requires only adding a new template directory:

```
prompts/
  podcast/outline.jinja       ← exists
  podcast/transcript.jinja    ← exists
  presentation/outline.jinja  ← needs to be created
  infographic/layout.jinja    ← needs to be created
```

### 2.6 The `lfnovo` Ecosystem Libraries

The maintainer (Luis Novo / `lfnovo`) has published a family of focused Python libraries that serve as Open Notebook's first-party dependencies:

| Library | PyPI | GitHub | Role |
|---|---|---|---|
| `podcast-creator` | https://pypi.org/project/podcast-creator/ | https://github.com/lfnovo/podcast-creator | Podcast artifact engine |
| `esperanto` | https://pypi.org/project/esperanto/ | https://github.com/lfnovo/esperanto | Unified LLM interface |
| `content-core` | https://pypi.org/project/content-core/ | https://github.com/lfnovo/content-core | Content extraction |
| `ai-prompter` | https://pypi.org/project/ai-prompter/ | https://github.com/lfnovo/ai-prompter | Jinja2 prompt rendering |
| `surreal-commands` | https://pypi.org/project/surreal-commands/ | https://github.com/lfnovo/surreal-commands | Background job queue |

**Key finding:** There is no `presentation-creator`, `slide-creator`, or `infographic-creator` library in this ecosystem. The gap in the library layer mirrors the gap in the application layer.

---

## 3. Module-by-Module Gap Analysis

---

### 3.1 Presentation / Slide Deck Generation

#### Status in Open Notebook
**Absent.** No code, no prompt templates, no domain models, no API endpoints related to slide or presentation generation exist anywhere in the codebase.

#### What NotebookLM Produces
- Two modes: "Presenter" (concise, bullet-point) and "Detailed" (comprehensive)
- Customisable length: short / default / long
- Exported as downloadable `.pptx` / Google Slides format
- Visually styled output with AI-selected imagery

#### External Modules Available

---

##### `python-pptx` — Core PPTX generation library
- **PyPI:** `python-pptx` (v1.0.2, August 2024)
- **GitHub:** https://github.com/scanny/python-pptx
- **License:** MIT
- **Stars:** ~3,300
- **Description:** The foundational library for creating `.pptx` files programmatically. Full control over slides, shapes, text boxes, tables, images. Does not require PowerPoint to be installed. LLMs output a structured JSON schema → python-pptx renders it.
- **Maintainability:** Production/Stable (Development Status 5). Excellent documentation.
- **Integration fit:** Drop-in; no LangChain dependency. Used as the render layer underneath all LangGraph orchestration approaches.

---

##### `langchain-deck` — HTML/CSS-first PPTX generation
- **PyPI:** `langchain-deck`
- **GitHub:** https://pypi.org/project/langchain-deck/
- **License:** Appears MIT
- **Description:** Treats PowerPoint generation as a rendering problem. Instead of manual coordinate calculations with python-pptx, it lets LLMs generate HTML/CSS (which they do extremely well), then converts to PPTX. Eliminates the need to define pixel-level positions and text wrapping logic.
- **Integration fit:** Excellent. Named explicitly for LangChain. Removes the most painful part of PPTX generation (coordinate arithmetic).

---

##### `llm_pptx_deck_builder` — Full LangGraph pipeline for research-backed slides
- **GitHub:** https://github.com/jc7k/llm_pptx_deck_builder
- **PyPI:** Not published (install from GitHub)
- **License:** MIT
- **Description:** A production-ready 6-node LangGraph pipeline: `research → load_docs → create_index → generate_outline → generate_content → create_presentation`. Integrates LlamaIndex for RAG, Brave Search for current facts, Phoenix for observability, and python-pptx for rendering. Includes citation tracking and anti-repetition validation.
- **Architecture:** The state machine pattern is identical to Open Notebook's own graphs. This is the closest architectural match available.
- **Integration fit:** Very high. The graph pattern is the same. Could be adapted in under a day.

**Reference tutorial:**
- https://medium.com/@gaddam.rahul.kumar/building-an-llm-powered-slide-deck-generator-with-langgraph-973aeaac0a06

---

##### `deck-generator-agent-skills` — Modern LangChain 1.1+ ReAct agent
- **GitHub:** https://github.com/jzamalloa1/deck-generator-agent-skills
- **License:** MIT
- **Description:** Production-ready ReAct agent using LangChain 1.1+ and LangGraph 1.0+ with PostgreSQL checkpointing and LangSmith deployment. Demonstrates the patterns recommended by LangChain for v1.x agent architectures.
- **Integration fit:** Good. Requires LangChain 1.1+ which Open Notebook already satisfies (`langchain>=1.2.0` per `pyproject.toml`).

---

##### `PPT-Agent` — Template-aware enterprise pipeline
- **GitHub:** https://github.com/Dishant22-ml/PPT-Agent-
- **License:** MIT
- **Description:** 4-stage pipeline: Slide Extractor (PPTX→XML) → Slide Selector (Groq LLM for narrative matching) → Slide Modifier (content updating) → PPT Generator (XML→PPTX). Supports brand-compliant templates with organisational storytelling patterns.
- **Integration fit:** Medium. More complex than needed for a start, but valuable for template compliance.

---

#### Implementation Pattern for Open Notebook

The architecture is already scaffolded. Adding slide generation requires:

1. **New domain model** in `open_notebook/domain/presentation.py`:
   ```python
   class SlideSpec(BaseModel):
       title: str
       bullet_points: list[str]
       speaker_notes: Optional[str]
   
   class PresentationSpec(BaseModel):
       title: str
       slides: list[SlideSpec]
       style: Literal["presenter", "detailed"] = "presenter"
   ```

2. **New prompt templates** in `prompts/presentation/outline.jinja` and `prompts/presentation/slides.jinja`

3. **New LangGraph** in `open_notebook/graphs/presentation.py` — 3 nodes: `plan_outline → generate_slides → render_pptx`

4. **New command** in `commands/presentation_commands.py` — identical structure to `podcast_commands.py`

5. **New API router** in `api/routers/presentations.py` + new service in `api/presentation_service.py`

6. **Add dependency:** `python-pptx>=1.0.2` or `langchain-deck` to `pyproject.toml`

---

### 3.2 Infographic Generation

#### Status in Open Notebook
**Absent.** No visual layout, no image rendering, no infographic logic exists.

#### What NotebookLM Produces
- Single-page visual summaries of source content
- Customisable: portrait/landscape/square, detail level, colour theme, visual style
- Exported as image (PNG) or PDF

#### External Modules Available

---

##### `WeasyPrint` — HTML/CSS to PDF/PNG conversion
- **PyPI:** `weasyprint`
- **GitHub:** https://github.com/Kozea/WeasyPrint
- **License:** BSD
- **Description:** The "Awesome Document Factory." Takes HTML/CSS input and renders it to high-quality PDF or images. Works perfectly with Jinja2 templates (which Open Notebook already uses via `ai-prompter`). The LLM generates a structured JSON spec → Jinja2 renders it as HTML → WeasyPrint outputs a PDF/PNG infographic.
- **Integration fit:** Excellent. The Jinja2 → WeasyPrint pipeline is the most natural fit for this codebase.

---

##### `Pillow` — Image composition and text rendering
- **PyPI:** `Pillow` (v12.2.0, April 2026)
- **GitHub:** https://github.com/python-pillow/Pillow
- **License:** HPND (permissive open source)
- **Stars:** 13,500+
- **Description:** The Python Imaging Library fork. Creates and manipulates images, renders text, draws shapes, composes layered graphics. Used for pixel-level infographic composition when WeasyPrint's web-rendering model is insufficient.
- **Integration fit:** Good. Requires more manual layout logic than WeasyPrint.

---

##### `ReportLab` — Programmatic PDF with embedded charts
- **PyPI:** `reportlab`
- **GitHub:** https://github.com/reportlab/reportlab
- **License:** BSD
- **Description:** Comprehensive PDF and graphics generation. High-level Graphics Library for vector graphics. Supports charts, diagrams, tables. Used when infographics must embed data visualisations.
- **Integration fit:** Good. More verbose API than WeasyPrint but more powerful for mixed-content layouts.

---

##### `Plotly` + `Kaleido` — Data-driven visual elements
- **PyPI:** `plotly` (v6.7.0), `kaleido`
- **GitHub:** https://github.com/plotly/plotly.py
- **License:** MIT
- **Description:** Plotly generates interactive and static data visualisations (30+ chart types). Kaleido enables static image export (PNG, SVG, PDF). Used as the data-visualisation engine inside infographic generation pipelines — charts, statistics panels, and graphs that make infographics compelling.
- **Integration fit:** Excellent. Plotly is already in the Python ecosystem and plays well with AI-generated structured data.

---

##### `CairoSVG` — SVG to raster/vector conversion
- **PyPI:** `cairosvg` (v2.9.0, March 2026)
- **GitHub:** https://github.com/Kozea/CairoSVG
- **License:** LGPL
- **Description:** Converts SVG (which LLMs can generate directly) to PNG, PDF, PostScript, EPS. Enables a pure-text pipeline: LLM generates SVG markup → CairoSVG renders it as PNG.
- **Integration fit:** Good. SVG is a text format, meaning an LLM can literally write an infographic layout as SVG code.

---

#### Recommended Pipeline for Infographic Generation

```
ContextBuilder (notebook sources + notes)
    ↓
LLM (provision_langchain_model) → structured JSON: {title, sections, stats, colour_theme}
    ↓
Jinja2 template (prompts/infographic/layout.html.jinja) → HTML/CSS
    ↓
WeasyPrint → PDF or PNG
    ↓
surreal-commands background job → stored in /data/infographics/
```

---

### 3.3 Mind Map Generation

#### Status in Open Notebook
**Absent.**

#### External Modules Available

---

##### `mindmap-generator` — LLM-native mind map generation
- **GitHub:** https://github.com/Dicklesworthstone/mindmap-generator
- **License:** MIT
- **Stars:** 211
- **Description:** Takes documents as input, uses LLMs (OpenAI, Claude, DeepSeek, Gemini) to extract hierarchical structure, outputs Mermaid syntax, interactive HTML, or Markdown outline. Supports the same providers as Open Notebook via Esperanto.
- **Integration fit:** Very high. Model-agnostic; can be wired directly to `provision_langchain_model`.

---

##### `brain_dump` — Markdown to mind map
- **PyPI:** `brain_dump` (v1.1.5)
- **GitHub:** https://github.com/Lucas-C/brain_dump
- **License:** GPL-3.0
- **Description:** Converts Markdown-like text to mind maps (PNG via Graphviz or WiseMapping-compatible XML). Works as a render layer: LLM produces structured Markdown → brain_dump renders it.
- **Integration fit:** Good for simple use cases; GPL licence may be a concern for proprietary deployments.

---

##### `markmap` (JavaScript, but Python-accessible)
- **GitHub:** https://github.com/markmap/markmap
- **Stars:** 12,700
- **Description:** The most polished mind map renderer available. Converts Markdown to interactive HTML mind maps. While JavaScript-native, it can be invoked from Python via `subprocess` or `playwright-python` for screenshot capture.
- **Integration fit:** Medium. Requires Node.js runtime or Playwright browser; adds infrastructure dependency.

---

##### `graphviz` — Low-level graph rendering
- **PyPI:** `graphviz`
- **GitHub:** https://github.com/xflr6/graphviz
- **License:** MIT
- **Description:** Python interface to Graphviz DOT language. LLM generates DOT syntax → graphviz renders PNG/SVG/PDF. Lower-level but extremely flexible.
- **Integration fit:** Good for custom layouts; requires Graphviz system binary.

---

### 3.4 Timeline Generation

#### Status in Open Notebook
**Absent.**

#### External Modules Available

---

##### `Plotly` — Gantt/timeline charts
- **PyPI:** `plotly`
- **Description:** `plotly.express.timeline()` generates interactive Gantt-style timelines from structured data with start/end dates and event labels. Exports to interactive HTML or static PNG.
- **Integration fit:** Excellent. LLM extracts dates and events from sources into structured JSON → Plotly renders the timeline.

---

##### `matplotlib` — Custom timeline visualisation
- **PyPI:** `matplotlib`
- **Description:** Lower-level but gives full control over timeline aesthetics. Used when Plotly's Gantt format does not match the desired visual style.
- **Integration fit:** Good. Already a common dependency in the Python scientific ecosystem.

---

### 3.5 Flashcard Generation

#### Status in Open Notebook
**Absent.**

#### External Modules Available

---

##### `genanki` — Anki deck generation
- **PyPI:** `genanki` (v0.13.1)
- **GitHub:** https://github.com/kerrickstaley/genanki
- **License:** MIT
- **Stars:** 2,600+
- **Description:** Programmatically generates Anki flashcard decks (`.apkg` format). Supports cloze deletions, media attachments, custom card models. The LLM generates Q&A pairs from source text → genanki serialises them to an Anki deck.
- **Integration fit:** Excellent. Pure Python, no heavy dependencies.

**Reference implementation:**
- https://github.com/mikkac/flashcards_generator — LangChain + OpenAI + genanki full pipeline

---

### 3.6 Quiz Generation

#### Status in Open Notebook
**Absent.**

#### External Modules Available

---

##### `qa-generator` — Multi-provider LLM quiz generation
- **PyPI:** `qa-generator` (v0.1.0, September 2025)
- **GitHub:** https://github.com/hemanth/qa-generator
- **License:** MIT
- **Description:** Generates QA pairs using LLMs (OpenAI, Ollama, Together, Groq, local endpoints) or rule-based NER. Supports difficulty levels (easy/medium/hard) and HuggingFace dataset output format.
- **Integration fit:** Excellent. Supports Ollama and Groq, which are native to Open Notebook via Esperanto.

---

##### `lmqg` — Fine-tuned T5 question generation
- **PyPI:** `lmqg`
- **GitHub:** https://github.com/asahi417/lm-question-generation
- **License:** MIT
- **Description:** Uses fine-tuned T5 models to generate question-answer pairs. Supports 9 languages. Three modes: QAG (end-to-end), QG (with answer hints), AE (answer extraction). Pre-trained models available on HuggingFace.
- **Integration fit:** Good for offline/self-hosted deployments where API costs matter.

---

##### `semantic-qa-gen` — Bloom's taxonomy-aware quiz generation
- **PyPI:** `semantic-qa-gen`
- **Description:** Generates QA pairs with cognitive level diversity (Bloom's taxonomy). Higher-quality output than simple QA generation.
- **Integration fit:** Good. Quality-focused alternative when quiz sophistication matters.

---

### 3.7 Study Guide & Briefing Document Generation

#### Status in Open Notebook
**Partially present via Transformations.** The `Transformation` system allows arbitrary prompt-driven text generation from source content. A user could manually create a "Study Guide" or "Briefing Document" transformation. However:

1. There are no pre-built transformation templates for these artifact types in the default database migrations.
2. The output is unstructured plain text/markdown — there is no schema, no formatting engine, and no dedicated export format.
3. The transformations system is entirely text-in → text-out; it has no awareness of document structure, sections, or downloadable output formats.

Relevant code:
```python
# open_notebook/domain/transformation.py (lines 8–15)
class Transformation(ObjectModel):
    table_name: ClassVar[str] = "transformation"
    name: str
    title: str
    description: str
    prompt: str          # ← This is the entire definition of the transformation
    apply_default: bool
```

The `Transformation` model is a single-field prompt. It produces markdown text. It cannot produce a structured PDF, a formatted `.docx`, or a visually styled document without additional tooling.

#### External Modules for Structured Document Output

---

##### `python-docx` — Word document generation
- **PyPI:** `python-docx` (v1.2.0, June 2025)
- **GitHub:** https://github.com/python-openxml/python-docx
- **License:** MIT
- **Description:** Creates and modifies `.docx` files programmatically. The LLM generates a structured study guide or briefing document as JSON → python-docx renders it as a properly formatted Word file with headings, sections, tables, and bullet points.
- **Integration fit:** Excellent. Same maintainer as python-pptx. Zero infrastructure requirements.

---

## 4. The Podcast Module as the Implementation Blueprint

The podcast module is the single most important reference for implementing any new artifact. Its architecture establishes the complete pattern:

```
open_notebook/podcasts/models.py      ← Domain models (EpisodeProfile, SpeakerProfile, PodcastEpisode)
api/podcast_service.py                ← Service layer (submit_generation_job, get_job_status)
commands/podcast_commands.py          ← Background command (generate_podcast_command)
api/routers/podcasts.py               ← API endpoints
prompts/podcast/outline.jinja         ← LLM prompt for structure
prompts/podcast/transcript.jinja      ← LLM prompt for content
```

The dependency chain for podcast generation is:

```python
# commands/podcast_commands.py (lines 19–23)
try:
    from podcast_creator import configure, create_podcast
except ImportError as e:
    logger.error(f"Failed to import podcast_creator: {e}")
    raise ValueError("podcast_creator library not available")
```

The `podcast-creator` library (`https://github.com/lfnovo/podcast-creator`) is the actual artifact engine. Open Notebook wraps it with:
- Profile management (database-stored configuration)
- Model credential resolution
- Background job submission
- Progress tracking via `surreal-commands`

**For any new artifact type, the exact same delegation pattern applies:**
```python
from presentation_creator import create_presentation  # ← library to be built/chosen
```

The entire Open Notebook wrapper infrastructure — job queue, profile management, API endpoint, frontend hooks — can be cloned from the podcast implementation. The only genuinely novel work is the artifact engine itself (the equivalent of `podcast-creator`), for which the external modules catalogued in Section 3 provide the building blocks.

---

## 5. Extraction Viability Assessment

### Can modules be extracted and used independently of Open Notebook?

| Concern | Assessment |
|---|---|
| **AI provisioning** | `provision_langchain_model()` depends on SurrealDB-stored model configs. Extractable with minor adaptation: replace DB lookup with env-var or config-file model selection. |
| **Context assembly** | `ContextBuilder` depends on `Source`, `Note`, `Notebook` domain models (SurrealDB). Extractable as a standalone RAG assembler by replacing domain model calls with any data source. |
| **Job queue** | `surreal-commands` is a first-party library; portable and decoupled from Open Notebook logic. |
| **Graph orchestration** | LangGraph graphs have **zero coupling** to Open Notebook internals other than the domain models they accept as input. Each graph is independently runnable. |
| **Prompt templates** | Pure Jinja2 files; zero coupling. |

**Verdict:** The core orchestration components (graphs, context builder, model provisioning) have **low-to-medium coupling** to the Open Notebook host. They can be extracted within a day of refactoring. The external rendering libraries (python-pptx, WeasyPrint, etc.) have **zero coupling** — they are entirely standalone.

### Is the current implementation of existing modules best-in-class?

| Module | Assessment |
|---|---|
| **Podcast generation** | The integration with `podcast-creator` is well-structured. The profile-based configuration is extensible. The async job queue pattern is correct. The main weakness is that `podcast-creator` is a private ecosystem dependency — if the library stagnates, the module stagnates with it. |
| **Transformation system** | Under-exploited for artifact generation. It is capable of producing study guides and briefing documents today but lacks structured output schemas and rendering layers. A structured output parser (Pydantic + LangChain's `.with_structured_output()`) would significantly improve it. |
| **RAG / Context** | `ContextBuilder` is solid and well-abstracted. Token-aware truncation and priority weighting are correctly implemented. |

---

## 6. Recommended Implementation Roadmap

Listed in order of implementation effort (ascending) and value (based on NotebookLM usage data).

### Tier 1 — Quick wins (1–3 days each)

| # | Artifact | Approach | Key Libraries |
|---|---|---|---|
| 1 | **Study Guide / Briefing Doc** | Extend Transformation system with structured Pydantic output + python-docx renderer | `python-docx` |
| 2 | **FAQ** | New Transformation-style graph with Q&A Pydantic schema; plain text or docx output | None (pure LLM) |
| 3 | **Flashcards** | New graph: source → LLM → Q&A pairs → genanki .apkg export | `genanki` |

### Tier 2 — Medium complexity (3–7 days each)

| # | Artifact | Approach | Key Libraries |
|---|---|---|---|
| 4 | **Slide Deck** | New LangGraph (plan → generate → render); Jinja2 for structure; python-pptx for rendering | `python-pptx`, optionally `langchain-deck` |
| 5 | **Mind Map** | New graph: source → LLM (Mermaid/DOT output) → graphviz/markmap render | `graphviz`, `mindmap-generator` |
| 6 | **Timeline** | New graph: source → LLM (event extraction) → Plotly timeline → PNG/HTML | `plotly`, `kaleido` |
| 7 | **Quiz** | New graph: source → LLM → MCQ schema → JSON or rendered PDF | `qa-generator`, `reportlab` |

### Tier 3 — Complex (1–2 weeks)

| # | Artifact | Approach | Key Libraries |
|---|---|---|---|
| 8 | **Infographic** | New graph: source → LLM (layout JSON) → Jinja2 HTML → WeasyPrint PDF/PNG | `weasyprint`, `plotly`, `Pillow` |
| 9 | **Video Overview** | Requires TTS + image generation + video assembly; significant new infrastructure | `moviepy`, `pillow`, TTS models |

---

## 7. Complete External Module Catalogue

### Presentation & Slides

| Library | PyPI | GitHub | License | LangGraph-ready | Notes |
|---|---|---|---|---|---|
| `python-pptx` | https://pypi.org/project/python-pptx/ | https://github.com/scanny/python-pptx | MIT | Via wrapper | Core PPTX engine; ~3,300 stars; v1.0.2 Aug 2024 |
| `python-docx` | https://pypi.org/project/python-docx/ | https://github.com/python-openxml/python-docx | MIT | Via wrapper | Word docs; v1.2.0 Jun 2025; same maintainer |
| `langchain-deck` | https://pypi.org/project/langchain-deck/ | (PyPI only) | MIT | ✅ Native | HTML/CSS→PPTX; avoids coordinate hell |
| `llm_pptx_deck_builder` | GitHub only | https://github.com/jc7k/llm_pptx_deck_builder | MIT | ✅ 6-node graph | Full LangGraph pipeline with RAG + citations |
| `deck-generator-agent-skills` | GitHub only | https://github.com/jzamalloa1/deck-generator-agent-skills | MIT | ✅ ReAct agent | LangChain 1.1+ / LangGraph 1.0+ |
| `PPT-Agent` | GitHub only | https://github.com/Dishant22-ml/PPT-Agent- | MIT | Via wrapper | Template-aware; brand compliance |
| `ai-presentation-generator` | GitHub only | https://github.com/JenilPoria/ai-presentation-generator | MIT | Via wrapper | Groq + Streamlit; fast prototype |

### Infographic & Visual Document

| Library | PyPI | GitHub | License | Notes |
|---|---|---|---|---|
| `weasyprint` | https://pypi.org/project/weasyprint/ | https://github.com/Kozea/WeasyPrint | BSD | HTML/CSS → PDF/PNG; ideal for Jinja2 pipelines |
| `reportlab` | https://pypi.org/project/reportlab/ | (official) | BSD | Programmatic PDF + charts; mature |
| `Pillow` | https://pypi.org/project/Pillow/ | https://github.com/python-pillow/Pillow | HPND | Image composition; v12.2.0 Apr 2026; 13,500 stars |
| `cairosvg` | https://pypi.org/project/CairoSVG/ | https://github.com/Kozea/CairoSVG | LGPL | SVG → PNG/PDF; v2.9.0 Mar 2026 |
| `plotly` | https://pypi.org/project/plotly/ | https://github.com/plotly/plotly.py | MIT | Interactive + static charts; v6.7.0 |
| `kaleido` | https://pypi.org/project/kaleido/ | (Plotly org) | MIT | Static image export for Plotly |
| `matplotlib` | https://pypi.org/project/matplotlib/ | https://github.com/matplotlib/matplotlib | PSF | Static scientific plots; 22,700 stars |
| `graphviz` | https://pypi.org/project/graphviz/ | https://github.com/xflr6/graphviz | MIT | DOT language → PNG/SVG/PDF |

### Mind Maps

| Library | PyPI | GitHub | License | Notes |
|---|---|---|---|---|
| `mindmap-generator` | GitHub only | https://github.com/Dicklesworthstone/mindmap-generator | MIT | LLM-native; OpenAI/Claude/Gemini; Mermaid + HTML output; 211 stars |
| `brain_dump` | https://pypi.org/project/brain_dump/ | https://github.com/Lucas-C/brain_dump | GPL-3.0 | Markdown → Graphviz PNG; v1.1.5 |
| `markmap` | npm only | https://github.com/markmap/markmap | MIT | JavaScript; 12,700 stars; best visual quality; needs Node.js |
| `pygraphviz` | https://pypi.org/project/pygraphviz/ | https://github.com/pygraphviz/pygraphviz | BSD | Python→Graphviz; lower-level |

### Flashcards

| Library | PyPI | GitHub | License | Notes |
|---|---|---|---|---|
| `genanki` | https://pypi.org/project/genanki/ | https://github.com/kerrickstaley/genanki | MIT | Anki `.apkg` generation; 2,600 stars; v0.13.1 |

**Reference implementation:** https://github.com/mikkac/flashcards_generator (LangChain + genanki)

### Quiz Generation

| Library | PyPI | GitHub | License | Notes |
|---|---|---|---|---|
| `qa-generator` | https://pypi.org/project/qa-generator/ | https://github.com/hemanth/qa-generator | MIT | Multi-provider LLM (OpenAI, Ollama, Groq); difficulty levels; v0.1.0 |
| `lmqg` | https://pypi.org/project/lmqg/ | https://github.com/asahi417/lm-question-generation | MIT | T5-based; 9 languages; offline-capable; 371 stars |
| `semantic-qa-gen` | https://pypi.org/project/semantic-qa-gen/ | — | — | Bloom's taxonomy levels; high quality |
| `groq-qa-generator` | https://pypi.org/project/groq-qa-generator/ | https://github.com/jcassady/groq-qa-generator | — | Groq API + LLaMA 3; CLI + library |

### Timelines

| Library | PyPI | Notes |
|---|---|---|
| `plotly` | https://pypi.org/project/plotly/ | `plotly.express.timeline()` — Gantt-style timeline; interactive HTML or static PNG |
| `matplotlib` | https://pypi.org/project/matplotlib/ | Custom timeline via horizontal bars; full aesthetic control |

### Structured LLM Output (cross-cutting)

| Library | PyPI | GitHub | License | Notes |
|---|---|---|---|---|
| `outlines` | https://pypi.org/project/outlines/ | https://github.com/dottxt-ai/outlines | Apache 2.0 | Guarantees structured JSON output from any LLM; Pydantic model support; critical for schema-driven artifact generation |

---

## Appendix: Key Reference Links

| Resource | URL |
|---|---|
| NotebookLM artifact documentation | https://support.google.com/notebooklm/answer/16758265 |
| NotebookLM slide deck guide (Google Blog) | https://blog.google/innovation-and-ai/models-and-research/google-labs/8-ways-to-make-the-most-out-of-slide-decks-in-notebooklm/ |
| LangGraph slide deck tutorial (Medium) | https://medium.com/@gaddam.rahul.kumar/building-an-llm-powered-slide-deck-generator-with-langgraph-973aeaac0a06 |
| Full-stack AI PPTX generator (Dev.to) | https://dev.to/copilotkit/how-to-build-an-ai-powered-powerpoint-generator-langchain-copilotkit-openai-nextjs-4c76 |
| Enterprise PowerPoint agent research (Gist) | https://gist.github.com/JewelsHovan/98fa3e5d0f361d2999e215873c3ad726 |
| LangChain multi-modal RAG on slides | https://blog.langchain.com/multi-modal-rag-template/ |
| lfnovo GitHub profile | https://github.com/lfnovo |
| podcast-creator PyPI | https://pypi.org/project/podcast-creator/ |
| esperanto PyPI | https://pypi.org/project/esperanto/ |
