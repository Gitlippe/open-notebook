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

# ---------------------------------------------------------------------------
# Parameterised builders (for prompts that need runtime configuration)
# ---------------------------------------------------------------------------


def build_faq_prompt(max_items: int = 10) -> str:
    """Return a FAQ prompt requesting ``max_items`` Q&A pairs."""
    return (
        "Generate a FAQ from the sources. Return STRICT JSON:\n"
        '{\n'
        '  "title": "FAQ: <topic>",\n'
        '  "items": [ {"question": "...", "answer": "complete, specific answer"} ]\n'
        '}\n'
        f"Generate {max_items} diverse Q&A pairs. "
        "Do not include commentary outside the JSON."
    )


# ---------------------------------------------------------------------------
# Slide-deck map/reduce variants
# ---------------------------------------------------------------------------

SLIDE_DECK_MAP_PROMPT = """Extract key informational content from the following source
chunk to contribute to a slide deck. Return STRICT JSON with this schema:
{
  "title": "deck title (infer from content if not explicit)",
  "subtitle": "one-line subtitle or null",
  "slides": [
    {
      "title": "slide title",
      "bullets": ["bullet 1", "bullet 2", "bullet 3"],
      "notes": "presenter speaker notes"
    }
  ]
}
Produce 3-5 slides representing the most important points in this chunk.
First slide should be a title/overview; include a conclusion if appropriate.
No commentary outside JSON."""

SLIDE_DECK_REDUCE_PROMPT = """You are synthesising partial slide deck extractions
from multiple source chunks into one coherent, non-redundant deck.
Return STRICT JSON with this schema:
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
Include 7-10 slides total. Remove duplicate or near-duplicate points.
Ensure logical narrative flow: title → body slides → conclusion.
No commentary outside JSON."""

PITCH_DECK_MAP_PROMPT = """Extract key content from this source chunk that would be
relevant for an investor pitch deck. Return STRICT JSON:
{
  "title": "deck title",
  "tagline": "one-line positioning or null",
  "slides": [
    {
      "title": "slide title",
      "bullets": ["bullet 1", "bullet 2"],
      "notes": "speaker notes"
    }
  ]
}
Produce 3-5 slides. Focus on facts, metrics, and claims relevant for investors.
No commentary outside JSON."""

PITCH_DECK_REDUCE_PROMPT = """Synthesise partial pitch deck extractions from multiple
source chunks into one coherent venture-style pitch deck.
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
Produce 8-12 slides. Remove redundancy. No commentary outside JSON."""

RESEARCH_REVIEW_MAP_PROMPT = """You are a skeptical practitioner reviewing a research
paper chunk. Extract relevant review points. Return STRICT JSON:
{
  "title": "Review: <topic>",
  "bluf": "one-sentence verdict on this chunk",
  "notable_authors": [],
  "affiliations": [],
  "short_take": "2-4 sentence summary",
  "why_we_care": {
    "direct_techniques": [],
    "cost_effectiveness": [],
    "limitations": []
  },
  "limitations": ["methodological limitations found"],
  "potential_applications": ["concrete use cases"],
  "resources": [{"label": "...", "url": "..."}]
}
No commentary outside JSON."""

RESEARCH_REVIEW_REDUCE_PROMPT = """Synthesise partial research review extractions into
one coherent, skeptical peer review. Consolidate findings, remove duplicates.
Return STRICT JSON:
{
  "title": "Research Review: <paper/topic title>",
  "bluf": "Bottom Line Up Front. Clear verdict.",
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
No add commentary outside the JSON."""

PAPER_FIGURE_MAP_PROMPT = """Extract quantitative data and key findings from this
source chunk suitable for visualisation in a research paper figure.
Return STRICT JSON:
{
  "title": "figure title",
  "chart_type": "bar|line|scatter",
  "x_label": "x axis label",
  "y_label": "y axis label",
  "series": [
    {
      "name": "series name",
      "data": [{"x": "category or value", "y": 0.0}]
    }
  ],
  "caption": "1-2 sentence figure caption"
}
If no numeric data is available, use reasonable inferred values and note it in caption.
No commentary outside JSON."""

PAPER_FIGURE_REDUCE_PROMPT = """Synthesise data extracted from multiple source chunks
into one clean, publication-ready figure specification.
Select the most informative data; prefer completeness over reduction.
Return STRICT JSON:
{
  "title": "figure title",
  "chart_type": "bar|line|scatter",
  "x_label": "x axis label",
  "y_label": "y axis label",
  "series": [
    {
      "name": "series name",
      "data": [{"x": "category or value", "y": 0.0}]
    }
  ],
  "caption": "1-2 sentence figure caption"
}
No commentary outside JSON."""

INFOGRAPHIC_MAP_PROMPT = """Extract key facts, statistics, and narrative points from
this source chunk for use in a single-page infographic.
Return STRICT JSON:
{
  "title": "bold, short headline",
  "subtitle": "one-sentence hook",
  "sections": [{"heading": "section title", "text": "1-2 sentence narrative"}],
  "stats": [{"value": "e.g. 82%", "label": "short label"}],
  "color_theme": "blue | green | orange | mono"
}
Produce 2-3 sections and 2-3 stats. No commentary outside JSON."""

INFOGRAPHIC_REDUCE_PROMPT = """Synthesise partial infographic specs from multiple
source chunks into one polished, single-page infographic layout.
Return STRICT JSON:
{
  "title": "bold, short headline",
  "subtitle": "one-sentence hook",
  "sections": [{"heading": "section title", "text": "1-2 sentence narrative"}],
  "stats": [{"value": "e.g. 82%", "label": "short label"}],
  "color_theme": "blue | green | orange | mono"
}
Produce 3-5 sections and 3-4 stats. Remove redundancy.
No commentary outside JSON."""

VIDEO_OVERVIEW_MAP_PROMPT = """Extract key narrative moments from this source chunk
to contribute to a narrated video overview. Return STRICT JSON matching this schema:
{
  "title": "video title",
  "total_duration_seconds": 60,
  "voice": {
    "provider": "openai",
    "voice_id": "alloy",
    "speaking_rate": 1.0
  },
  "beats": [
    {
      "beat_index": 1,
      "duration_seconds": 20,
      "narration_script": "Full, verbatim spoken narration. Conversational, reads naturally aloud.",
      "visual_prompt": "Specific image generation prompt: composition, style, colors, key elements.",
      "alt_text": "One-sentence accessibility description of the visual."
    }
  ]
}
Produce 2-3 beats, each 10-40 seconds. Focus on vivid, natural narration and specific visuals.
total_duration_seconds should equal the sum of all beat duration_seconds.
No commentary outside JSON."""

VIDEO_OVERVIEW_REDUCE_PROMPT = """Synthesise video beat extractions from multiple
source chunks into one coherent, well-paced narrated video spec.
Return STRICT JSON matching this schema:
{
  "title": "video title",
  "total_duration_seconds": 120,
  "voice": {
    "provider": "openai",
    "voice_id": "alloy",
    "speaking_rate": 1.0
  },
  "beats": [
    {
      "beat_index": 1,
      "duration_seconds": 20,
      "narration_script": "Full spoken narration (2-4 sentences, conversational).",
      "visual_prompt": "Detailed image generation prompt describing the visual scene.",
      "alt_text": "One-sentence accessibility description."
    }
  ]
}
Produce 4-10 beats. Ensure beat_index values are sequential starting at 1.
Remove redundancy; ensure logical narrative arc (intro -> body -> conclusion).
total_duration_seconds must equal the sum of all beat duration_seconds.
No commentary outside JSON."""

# ---------------------------------------------------------------------------
# Data tables map/reduce prompts (Stream C — data_tables.py)
# ---------------------------------------------------------------------------

DATA_TABLES_MAP_PROMPT = """Extract all tabular data, comparisons, metrics, and
structured lists from this source chunk. Return STRICT JSON:
{
  "tables": [
    {
      "title": "descriptive table title",
      "columns": ["Column 1", "Column 2", "Column 3"],
      "rows": [
        ["value 1a", "value 1b", "value 1c"],
        ["value 2a", "value 2b", "value 2c"]
      ],
      "caption": "optional footnote or source attribution, or null"
    }
  ]
}
Include at least 1 table. Produce one table per distinct dataset found.
Preserve numeric types in rows where possible (use numbers, not strings for numerics).
If no tabular data is present, create one table with key facts: columns ["Attribute", "Value"].
No commentary outside JSON."""

DATA_TABLES_REDUCE_PROMPT = """Synthesise tabular data extracted from multiple source
chunks into a clean, deduplicated collection of tables.
Return STRICT JSON:
{
  "tables": [
    {
      "title": "descriptive table title",
      "columns": ["Column 1", "Column 2"],
      "rows": [
        ["value 1a", "value 1b"],
        ["value 2a", "value 2b"]
      ],
      "caption": "optional footnote or source attribution, or null"
    }
  ]
}
Merge tables that cover the same topic into one. Remove duplicate rows.
Ensure every row in each table has the same number of cells as the columns list.
No commentary outside JSON."""


# ---------------------------------------------------------------------------
# <BATCH B> Stream B parameterised prompt builders (alphabetical).
# Each function returns a ready-to-use instructions string for use with
# combine_prompts() and chunked_generate().
# ---------------------------------------------------------------------------


def build_briefing_prompt(audience: str = "Executive") -> str:
    """Return the BLUF executive briefing instruction block (matches BriefingSchema)."""
    return (
        f"You are a senior analyst writing for a {audience} audience. "
        "Produce a concise BLUF (Bottom Line Up Front) executive briefing from "
        "the provided sources.\n\n"
        "Return a JSON object matching this schema exactly:\n"
        "{\n"
        '  "title": "short, descriptive title",\n'
        '  "audience": "short phrase describing ideal reader",\n'
        '  "bluf": "single most-important insight in one crisp sentence",\n'
        '  "key_points": ["3-5 sharp bullets summarising important findings"],\n'
        '  "supporting_details": ["2-4 bullets with data points or direct evidence"],\n'
        '  "action_items": ["2-4 crisp, specific, actionable items for the reader"],\n'
        '  "keywords": ["5-8 subject tags"]\n'
        "}\n\n"
        "Requirements:\n"
        "- BLUF must capture the SINGLE most important takeaway.\n"
        "- Action items must start with a verb and be specific.\n"
        "- Do not pad with filler; every bullet must add unique value.\n"
        "- Do not include any text outside the JSON object."
    )


def build_flashcards_prompt(card_count: int = 12) -> str:
    """Return the Anki flashcard instruction block (matches FlashcardsSchema)."""
    return (
        "You are an expert instructional designer. Create an Anki-compatible "
        "flashcard deck from the provided sources.\n\n"
        "Return a JSON object matching this schema exactly:\n"
        "{\n"
        '  "title": "Flashcards: <topic>",\n'
        '  "cards": [\n'
        '    {"front": "question or cloze prompt",\n'
        '     "back": "complete answer with explanation",\n'
        '     "tags": ["topic-tag-1", "topic-tag-2"]}\n'
        "  ]\n"
        "}\n\n"
        f"Requirements:\n"
        f"- Generate approximately {card_count} cards.\n"
        "- Each card must test a SINGLE atomic concept (not compound).\n"
        "- Vary cognitive levels: recall, comprehension, application, analysis.\n"
        "- Front should be phrased as a question or completion prompt.\n"
        "- Back must be self-contained (no external references required).\n"
        "- Tags should be 1-3 lowercase hyphenated strings.\n"
        "- Do not include any text outside the JSON object."
    )


def build_mindmap_prompt() -> str:
    """Return the mind map instruction block (matches MindMapSchema)."""
    return (
        "You are a knowledge-synthesis expert. Produce a hierarchical mind map "
        "that captures the key concepts from the provided sources.\n\n"
        "Return a JSON object matching this schema exactly:\n"
        "{\n"
        '  "central_topic": "concise name for the central node",\n'
        '  "branches": [\n'
        '    {"label": "primary theme or concept",\n'
        '     "children": ["sub-point 1", "sub-point 2", "sub-point 3"]}\n'
        "  ]\n"
        "}\n\n"
        "Requirements:\n"
        "- 5-7 top-level branches.\n"
        "- Each branch must have 2-5 distinct children.\n"
        "- Branches must be mutually exclusive (no overlapping concepts).\n"
        "- Labels must be short (<=6 words) - they are node labels, not sentences.\n"
        "- Do not include any text outside the JSON object."
    )


def build_quiz_prompt(question_count: int = 6) -> str:
    """Return the multiple-choice quiz instruction block (matches QuizSchema)."""
    return (
        "You are a test-design expert. Create a rigorous multiple-choice quiz "
        "from the provided sources.\n\n"
        "Return a JSON object matching this schema exactly:\n"
        "{\n"
        '  "title": "Quiz: <topic>",\n'
        '  "questions": [\n'
        '    {"question": "clear, single-focus question",\n'
        '     "options": ["option A", "option B", "option C", "option D"],\n'
        '     "answer_index": 0,\n'
        '     "explanation": "why the correct option is correct"}\n'
        "  ]\n"
        "}\n\n"
        f"Requirements:\n"
        f"- Generate approximately {question_count} questions.\n"
        "- Each question must have exactly 4 options.\n"
        "- ``answer_index`` is 0-based (0-3).\n"
        "- Distractors must be plausible, not obviously wrong.\n"
        "- Only ONE option should be unambiguously correct.\n"
        "- Vary difficulty: recall, application, analysis.\n"
        "- Do not include any text outside the JSON object."
    )


def build_study_guide_prompt(depth: str = "standard") -> str:
    """Return the study guide instruction block (matches StudyGuideSchema)."""
    depth_guidance = {
        "brief": "Keep sections concise - 3 objectives, 4 concepts, 3 glossary terms.",
        "standard": "Aim for 4-6 objectives, 5-8 concepts, 5-8 glossary terms.",
        "deep": "Be thorough - 6+ objectives, 8+ concepts, 8+ glossary terms, 6 discussion questions.",
    }.get(depth, "Aim for 4-6 objectives, 5-8 concepts, 5-8 glossary terms.")
    return (
        "You are a senior instructional designer. Build a comprehensive study guide "
        "from the provided sources.\n\n"
        "Return a JSON object matching this schema exactly:\n"
        "{\n"
        '  "title": "Study Guide: <topic>",\n'
        '  "overview": "2-4 sentence summary of what will be covered",\n'
        '  "learning_objectives": ["objective starting with an action verb"],\n'
        '  "key_concepts": ["concise self-contained concept sentence"],\n'
        '  "glossary": [{"term": "term", "definition": "one-sentence definition"}],\n'
        '  "discussion_questions": ["open-ended question"],\n'
        '  "further_reading": ["optional follow-up topic or resource"]\n'
        "}\n\n"
        f"Depth setting: {depth}. {depth_guidance}\n"
        "Requirements:\n"
        "- Learning objectives start with Bloom taxonomy verbs (Identify, Explain, Apply).\n"
        "- Glossary definitions must be self-contained: no 'see above' references.\n"
        "- Discussion questions must be open-ended and thought-provoking.\n"
        "- Do not include any text outside the JSON object."
    )


def build_timeline_prompt() -> str:
    """Return the chronological timeline instruction block (matches TimelineSchema)."""
    return (
        "You are a historian and research analyst. Extract a precise chronological "
        "timeline from the provided sources.\n\n"
        "Return a JSON object matching this schema exactly:\n"
        "{\n"
        '  "title": "Timeline: <descriptive topic name>",\n'
        '  "events": [\n'
        '    {"date": "ISO date or free-form year/period",\n'
        '     "event": "what happened - one clear, specific sentence",\n'
        '     "significance": "why this event matters in context"}\n'
        "  ]\n"
        "}\n\n"
        "Requirements:\n"
        "- Include 5-15 events, ordered chronologically (earliest first).\n"
        "- Dates must be as precise as the sources allow; never fabricate dates.\n"
        "- Each event description must be factually grounded in the sources.\n"
        "- Significance field must explain WHY the event matters, not just restate it.\n"
        "- Do not include any text outside the JSON object."
    )


# </BATCH B>

# ---------------------------------------------------------------------------
# <BATCH C> Stream C map/reduce prompts (alphabetical within batch).
# Owners: slide_deck, pitch_deck, research_review, paper_figure, infographic,
#         video_overview, data_tables.
# ---------------------------------------------------------------------------

DATA_TABLES_MAP_PROMPT = """Extract all tabular data, comparisons, metrics, and
structured lists from this source chunk. Return STRICT JSON:
{
  "tables": [
    {
      "title": "descriptive table title",
      "columns": ["Column 1", "Column 2", "Column 3"],
      "rows": [
        ["value 1a", "value 1b", "value 1c"],
        ["value 2a", "value 2b", "value 2c"]
      ],
      "caption": "optional footnote or source attribution, or null"
    }
  ]
}
Include at least 1 table. Produce one table per distinct dataset found.
Preserve numeric types in rows where possible.
If no tabular data is present, create one table with key facts: columns ["Attribute", "Value"].
No commentary outside JSON."""

DATA_TABLES_REDUCE_PROMPT = """Synthesise tabular data extracted from multiple source
chunks into a clean, deduplicated collection of tables.
Return STRICT JSON:
{
  "tables": [
    {
      "title": "descriptive table title",
      "columns": ["Column 1", "Column 2"],
      "rows": [
        ["value 1a", "value 1b"],
        ["value 2a", "value 2b"]
      ],
      "caption": "optional footnote or source attribution, or null"
    }
  ]
}
Merge tables that cover the same topic into one. Remove duplicate rows.
Ensure every row has the same number of cells as the columns list.
No commentary outside JSON."""

INFOGRAPHIC_MAP_PROMPT = """Extract key facts, statistics, and narrative points from
this source chunk for use in a single-page infographic.
Return STRICT JSON:
{
  "title": "bold, short headline",
  "subtitle": "one-sentence hook",
  "sections": [{"heading": "section title", "text": "1-2 sentence narrative"}],
  "stats": [{"value": "e.g. 82%", "label": "short label"}],
  "color_theme": "blue"
}
Produce 2-3 sections and 2-3 stats. color_theme must be one of: blue, green, orange, mono.
No commentary outside JSON."""

INFOGRAPHIC_REDUCE_PROMPT = """Synthesise partial infographic specs from multiple
source chunks into one polished, single-page infographic layout.
Return STRICT JSON:
{
  "title": "bold, short headline",
  "subtitle": "one-sentence hook",
  "sections": [{"heading": "section title", "text": "1-2 sentence narrative"}],
  "stats": [{"value": "e.g. 82%", "label": "short label"}],
  "color_theme": "blue"
}
Produce 3-5 sections and 3-4 stats. Remove redundancy.
color_theme must be one of: blue, green, orange, mono.
No commentary outside JSON."""

PAPER_FIGURE_MAP_PROMPT = """Extract quantitative data and key findings from this
source chunk suitable for visualisation in a research paper figure.
Return STRICT JSON:
{
  "title": "figure title",
  "chart_type": "bar",
  "x_label": "x axis label",
  "y_label": "y axis label",
  "series": [
    {
      "name": "series name",
      "data": [{"x": "category or value", "y": 0.0}]
    }
  ],
  "caption": "1-2 sentence figure caption"
}
chart_type must be one of: bar, line, scatter.
If no numeric data is available, use reasonable inferred values and note it in caption.
No commentary outside JSON."""

PAPER_FIGURE_REDUCE_PROMPT = """Synthesise data extracted from multiple source chunks
into one clean, publication-ready figure specification.
Return STRICT JSON:
{
  "title": "figure title",
  "chart_type": "bar",
  "x_label": "x axis label",
  "y_label": "y axis label",
  "series": [
    {
      "name": "series name",
      "data": [{"x": "category or value", "y": 0.0}]
    }
  ],
  "caption": "1-2 sentence figure caption"
}
chart_type must be one of: bar, line, scatter. Select the most informative data.
No commentary outside JSON."""

PITCH_DECK_MAP_PROMPT = """Extract key content from this source chunk that would be
relevant for an investor pitch deck. Return STRICT JSON:
{
  "title": "deck title",
  "tagline": "one-line positioning",
  "slides": [
    {
      "title": "slide title",
      "bullets": ["bullet 1", "bullet 2"],
      "notes": "speaker notes"
    }
  ]
}
Produce 3-5 slides. Focus on facts, metrics, and claims relevant for investors.
No commentary outside JSON."""

PITCH_DECK_REDUCE_PROMPT = """Synthesise partial pitch deck extractions from multiple
source chunks into one coherent venture-style pitch deck.
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
Produce 8-12 slides. Remove redundancy. No commentary outside JSON."""

RESEARCH_REVIEW_MAP_PROMPT = """You are a skeptical practitioner reviewing a research
paper chunk. Extract relevant review points. Return STRICT JSON:
{
  "title": "Review: <topic>",
  "bluf": "one-sentence verdict on this chunk",
  "notable_authors": [],
  "affiliations": [],
  "short_take": "2-4 sentence summary",
  "why_we_care": {
    "direct_techniques": [],
    "cost_effectiveness": [],
    "limitations": []
  },
  "limitations": ["methodological limitations found"],
  "potential_applications": ["concrete use cases"],
  "resources": [{"label": "...", "url": "..."}]
}
No commentary outside JSON."""

RESEARCH_REVIEW_REDUCE_PROMPT = """Synthesise partial research review extractions into
one coherent, skeptical peer review. Consolidate findings, remove duplicates.
Return STRICT JSON:
{
  "title": "Research Review: <paper/topic title>",
  "bluf": "Bottom Line Up Front. Clear verdict.",
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
No commentary outside JSON."""

SLIDE_DECK_MAP_PROMPT = """Extract key informational content from the following source
chunk to contribute to a slide deck. Return STRICT JSON:
{
  "title": "deck title (infer from content if not explicit)",
  "subtitle": "one-line subtitle or null",
  "slides": [
    {
      "title": "slide title",
      "bullets": ["bullet 1", "bullet 2", "bullet 3"],
      "notes": "presenter speaker notes"
    }
  ]
}
Produce 3-5 slides representing the most important points in this chunk.
No commentary outside JSON."""

SLIDE_DECK_REDUCE_PROMPT = """Synthesise partial slide deck extractions from multiple
source chunks into one coherent, non-redundant deck.
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
Include 7-10 slides total. Remove duplicate or near-duplicate points.
Ensure logical narrative flow: title -> body slides -> conclusion.
No commentary outside JSON."""

VIDEO_OVERVIEW_MAP_PROMPT = """Extract key narrative moments from this source chunk
to contribute to a narrated video overview. Return STRICT JSON:
{
  "title": "video title",
  "total_duration_seconds": 60,
  "voice": {
    "provider": "openai",
    "voice_id": "alloy",
    "speaking_rate": 1.0
  },
  "beats": [
    {
      "beat_index": 1,
      "duration_seconds": 20,
      "narration_script": "Full, verbatim spoken narration. Conversational, reads naturally aloud.",
      "visual_prompt": "Specific image generation prompt: composition, style, colors, key elements.",
      "alt_text": "One-sentence accessibility description of the visual."
    }
  ]
}
Produce 2-3 beats, each 10-40 seconds. Focus on vivid, natural narration and specific visuals.
total_duration_seconds should equal the sum of all beat duration_seconds.
voice.provider must be openai or elevenlabs.
No commentary outside JSON."""

VIDEO_OVERVIEW_REDUCE_PROMPT = """Synthesise video beat extractions from multiple
source chunks into one coherent, well-paced narrated video spec.
Return STRICT JSON:
{
  "title": "video title",
  "total_duration_seconds": 120,
  "voice": {
    "provider": "openai",
    "voice_id": "alloy",
    "speaking_rate": 1.0
  },
  "beats": [
    {
      "beat_index": 1,
      "duration_seconds": 20,
      "narration_script": "Full spoken narration (2-4 sentences, conversational).",
      "visual_prompt": "Detailed image generation prompt describing the visual scene.",
      "alt_text": "One-sentence accessibility description."
    }
  ]
}
Produce 4-10 beats. Ensure beat_index values are sequential starting at 1.
Remove redundancy; ensure logical narrative arc (intro -> body -> conclusion).
total_duration_seconds must equal the sum of all beat duration_seconds.
voice.provider must be openai or elevenlabs.
No commentary outside JSON."""

# </BATCH C>
