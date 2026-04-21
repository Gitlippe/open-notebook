# Open Notebook — Artifact Generation Agent Demos

This directory contains self-contained demo scripts for each of the twelve
artifact types that Open Notebook can generate from source material. Every
demo is a small end-to-end "agent" that:

1. Loads one or more source documents.
2. Calls the matching artifact generator.
3. Writes the output into `demos/_output/<demo_name>/`.
4. Prints a summary of what it produced.

All demos run offline by default — they use the built-in heuristic
extractor so you can see the full pipeline even without AI API keys. To
let the agents use your configured AI provider instead, set:

```bash
export ARTIFACT_USE_LLM=1
# plus your provider key, e.g. OPENAI_API_KEY=...
```

## Run all demos

```bash
uv run python demos/run_all_demos.py
```

## Run a single demo

Each file has a `main()` coroutine and a CLI:

```bash
uv run python demos/demo_briefing.py
uv run python demos/demo_slide_deck.py
```

## Demos

| # | Demo | Artifact | What it shows |
|---|------|----------|---------------|
| 1 | `demo_briefing.py` | Briefing (BLUF) | Executive summary for a product-launch memo |
| 2 | `demo_study_guide.py` | Study guide | Learning objectives and glossary from a tutorial |
| 3 | `demo_faq.py` | FAQ | Q&A derived from a product announcement |
| 4 | `demo_research_review.py` | Research review | Skeptical review of an AI paper (the Training-Free GRPO example) |
| 5 | `demo_flashcards.py` | Flashcards | Anki `.apkg` deck from a vocabulary list |
| 6 | `demo_quiz.py` | Quiz | MCQ quiz from a textbook chapter |
| 7 | `demo_mindmap.py` | Mind map | Mermaid + DOT + PNG mind map of a domain |
| 8 | `demo_timeline.py` | Timeline | Chronological PNG timeline of key events |
| 9 | `demo_infographic.py` | Infographic | Single-page PNG stat-heavy summary |
| 10 | `demo_slide_deck.py` | Slide deck | Multi-slide `.pptx` informational deck |
| 11 | `demo_pitch_deck.py` | Pitch deck | Venture-style `.pptx` pitch deck |
| 12 | `demo_paper_figure.py` | Paper figure | Publication-style comparison chart |

Additionally `demo_podcast_integration.py` shows how to combine podcast
generation (existing feature) with one of the new artifacts in a single
workflow.
