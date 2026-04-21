"""Canonical prompt templates for each artifact type.

Keeping the prompts inline (rather than as separate Jinja files) makes the
package dependency-free during tests and ensures demos work without any
file-system setup. The LLM layer accepts the combined string directly.
"""
from __future__ import annotations

BRIEFING_PROMPT = """You are a senior analyst. Produce a concise executive briefing
(a BLUF) from the provided sources. Return STRICT JSON with this schema:
{
  "title": "short, descriptive title",
  "audience": "short phrase describing ideal reader",
  "bluf": "Bottom Line Up Front sentence capturing the single most important insight",
  "key_points": ["3-5 sharp bullets each summarising an important finding"],
  "supporting_details": ["2-4 bullets with data points or direct evidence"],
  "action_items": ["2-4 crisp action items for the reader"],
  "keywords": ["5-8 tags"]
}
Do not include commentary outside the JSON."""

STUDY_GUIDE_PROMPT = """You are an instructional designer. Build a structured study
guide from the sources. Return STRICT JSON with this schema:
{
  "title": "Study Guide: <topic>",
  "overview": "2-4 sentence summary of the subject",
  "learning_objectives": ["4-6 goals, each starting with a verb"],
  "key_concepts": ["5-8 concepts, each a self-contained sentence"],
  "glossary": [{"term": "...", "definition": "one-sentence definition"}],
  "discussion_questions": ["4-6 open-ended questions"],
  "further_reading": ["optional list of suggested follow-up topics"]
}
Do not include commentary outside the JSON."""

FAQ_PROMPT = """Generate a FAQ from the sources. Return STRICT JSON:
{
  "title": "FAQ: <topic>",
  "items": [ {"question": "...", "answer": "complete, specific answer"} ]
}
Generate 6-10 diverse Q&A pairs. Do not include commentary outside the JSON."""

RESEARCH_REVIEW_PROMPT = """You are writing a brutally honest peer-level research
review for internal consumption. Follow the tone of a skeptical practitioner:
short, direct, identifying both the strengths and the methodological weaknesses.
Return STRICT JSON:
{
  "title": "Research Review: <paper/topic title>",
  "bluf": "Bottom Line Up Front. Begin with a clear verdict.",
  "notable_authors": ["Author One", "Author Two"],
  "affiliations": ["Affiliation 1"],
  "short_take": "3-6 sentence summary in plain language",
  "why_we_care": {
    "direct_techniques": ["concrete techniques we could adopt"],
    "cost_effectiveness": ["cost/ROI considerations"],
    "limitations": ["critical flaws or open questions"]
  },
  "limitations": ["explicit methodological limitations"],
  "potential_applications": ["2-5 concrete internal use cases"],
  "resources": [{"label": "arXiv", "url": "..."}]
}
Do not add commentary outside the JSON."""

FLASHCARDS_PROMPT = """Create an Anki-style flashcard deck from the sources.
Return STRICT JSON:
{
  "title": "Flashcards: <topic>",
  "cards": [
    {"front": "question or cloze", "back": "answer/explanation",
     "tags": ["topic"]}
  ]
}
Generate 10-15 cards with varied cognitive levels (recall, application,
analysis). Do not include commentary outside the JSON."""

QUIZ_PROMPT = """Create a multiple-choice quiz from the sources.
Return STRICT JSON:
{
  "title": "Quiz: <topic>",
  "questions": [
    {
      "question": "clear, single-focus question",
      "options": ["option 0", "option 1", "option 2", "option 3"],
      "answer_index": 0,
      "explanation": "why the correct option is correct"
    }
  ]
}
Generate 5-10 questions. Ensure ``answer_index`` is a 0-based integer.
Do not include commentary outside the JSON."""

MINDMAP_PROMPT = """Produce a hierarchical mind map of the sources.
Return STRICT JSON:
{
  "central_topic": "top-level node",
  "branches": [
    {
      "label": "primary theme",
      "children": ["sub-point 1", "sub-point 2", "sub-point 3"]
    }
  ]
}
5-7 branches. Each branch should have 2-5 children. No commentary outside JSON."""

TIMELINE_PROMPT = """Extract a chronological timeline from the sources.
Return STRICT JSON:
{
  "title": "Timeline: <topic>",
  "events": [
    {"date": "ISO or free-form date/year", "event": "what happened; one sentence"}
  ]
}
Include 5-12 events, earliest first. No commentary outside JSON."""

INFOGRAPHIC_PROMPT = """Design a single-page infographic layout spec.
Return STRICT JSON:
{
  "title": "bold, short headline",
  "subtitle": "one-sentence hook",
  "sections": [{"heading": "section title", "text": "1-2 sentence narrative"}],
  "stats": [{"value": "e.g. 82%", "label": "short label"}],
  "color_theme": "blue | green | orange | mono"
}
Produce 3-5 sections and 3-4 stats. No commentary outside JSON."""

SLIDE_DECK_PROMPT = """Design an informational slide deck.
Return STRICT JSON:
{
  "title": "deck title",
  "subtitle": "short subtitle",
  "slides": [
    {
      "title": "slide title",
      "bullets": ["bullet 1", "bullet 2", "bullet 3"],
      "notes": "presenter speaker notes"
    }
  ]
}
Include 7-10 slides. First slide is the title; last slide is the conclusion.
No commentary outside JSON."""

PITCH_DECK_PROMPT = """Build a venture-style pitch deck from the material.
Use the canonical structure: Cover, Problem, Solution, Market, Product,
Business Model, Traction, Competition, Team, Financials, Ask.
Return STRICT JSON:
{
  "title": "deck title",
  "tagline": "one-line positioning",
  "slides": [
    {
      "title": "slide title",
      "bullets": ["..."],
      "notes": "presenter notes"
    }
  ]
}
Produce 8-12 slides. No commentary outside JSON."""

PAPER_FIGURE_PROMPT = """Design a figure to accompany a research paper based on the
sources. Select the simplest chart type that communicates the core result.
Return STRICT JSON:
{
  "title": "figure title",
  "chart_type": "bar|line|scatter",
  "x_label": "x axis label",
  "y_label": "y axis label",
  "series": [
    {
      "name": "series name",
      "data": [{"x": "category or number", "y": 0.0}]
    }
  ],
  "caption": "1-2 sentence figure caption"
}
If numeric data is not available in the sources, invent reasonable
placeholder values and say so in the caption. No commentary outside JSON."""
