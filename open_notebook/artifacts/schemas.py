"""Strict Pydantic schemas for structured LLM output, per artifact type.

Every schema is the *contract* between the LLM and the renderer. Field
docstrings serve double duty as prompt hints — ``with_structured_output``
surfaces them to the model verbatim in most LangChain providers.
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


# ======================================================================
# Intermediate analysis schemas (shared across multi-step pipelines)
# ======================================================================

class Claim(BaseModel):
    """A single factual claim extracted from the source material."""

    text: str = Field(..., description="The claim, stated precisely in one sentence.")
    evidence: str = Field(
        ...,
        description=(
            "Direct quote or paraphrase from the source that supports the claim. "
            "Max ~30 words."
        ),
    )
    importance: Literal["critical", "high", "medium", "low"] = Field(
        ..., description="Importance of this claim for the intended artifact."
    )
    category: str = Field(
        ...,
        description=(
            "Short category tag, e.g. 'methodology', 'result', 'limitation', "
            "'market', 'quote', 'metric'."
        ),
    )


class ClaimSet(BaseModel):
    """The LLM's initial pass over the source: extract what is there."""

    topic: str = Field(..., description="One-line topic description.")
    purpose: str = Field(
        ...,
        description="What is the source trying to accomplish / argue / announce?",
    )
    audience_hint: str = Field(
        ..., description="Who is the source itself targeted at?"
    )
    claims: List[Claim] = Field(
        ...,
        min_length=5,
        description="5-20 atomic claims with evidence pointers.",
    )
    numeric_facts: List[str] = Field(
        default_factory=list,
        description="Any numeric/statistical facts (include units and context).",
    )
    named_entities: List[str] = Field(
        default_factory=list,
        description="People, orgs, products, places, papers explicitly mentioned.",
    )


class Critique(BaseModel):
    """Self-critique output used to drive a refinement pass."""

    issues: List[str] = Field(
        default_factory=list,
        description=(
            "Specific, actionable problems with the draft. Point to the exact "
            "claim or section; do not generalise."
        ),
    )
    missing: List[str] = Field(
        default_factory=list,
        description="Important facts from the source that are absent from the draft.",
    )
    redundancies: List[str] = Field(
        default_factory=list,
        description="Items in the draft that repeat each other or say nothing.",
    )
    suggested_edits: List[str] = Field(
        default_factory=list,
        description="Concrete rewrites or additions to apply next pass.",
    )
    quality_score: int = Field(
        ..., ge=1, le=10,
        description="Overall quality of the draft on a 1-10 scale.",
    )


# ======================================================================
# Briefing / BLUF
# ======================================================================

class Briefing(BaseModel):
    """Executive briefing structured for BLUF-style consumption."""

    title: str = Field(..., description="8-14 word concrete title.")
    audience: str = Field(..., description="Specific intended reader.")
    bluf: str = Field(
        ...,
        min_length=40,
        description=(
            "Bottom Line Up Front. A single sentence capturing the single most "
            "important takeaway; no hedging, no preamble."
        ),
    )
    key_points: List[str] = Field(
        ..., min_length=3, max_length=6,
        description=(
            "3-6 sharp bullets. Each is a self-contained declarative sentence "
            "with a concrete fact or decision-relevant insight."
        ),
    )
    supporting_details: List[str] = Field(
        ..., min_length=2, max_length=5,
        description=(
            "2-5 data-bearing bullets (numbers, dates, names). Only include "
            "evidence drawn from the source."
        ),
    )
    action_items: List[str] = Field(
        ..., min_length=2, max_length=5,
        description=(
            "2-5 imperative action items. Each starts with a verb and is "
            "concretely executable by the reader."
        ),
    )
    risks: List[str] = Field(
        default_factory=list, max_length=4,
        description="0-4 risks / dependencies explicitly called out in the source.",
    )
    keywords: List[str] = Field(
        ..., min_length=3, max_length=10,
        description="3-10 search-ready topic tags.",
    )


# ======================================================================
# Study guide
# ======================================================================

class GlossaryItem(BaseModel):
    term: str
    definition: str = Field(..., min_length=15)


class LearningObjective(BaseModel):
    bloom_level: Literal[
        "remember", "understand", "apply", "analyze", "evaluate", "create"
    ] = Field(..., description="Bloom's taxonomy level for this objective.")
    statement: str = Field(
        ..., min_length=10,
        description="An objective starting with a verb appropriate to the bloom level.",
    )


class StudyGuide(BaseModel):
    title: str
    overview: str = Field(..., min_length=100)
    prerequisites: List[str] = Field(default_factory=list, max_length=5)
    learning_objectives: List[LearningObjective] = Field(..., min_length=4, max_length=8)
    key_concepts: List[str] = Field(..., min_length=5, max_length=10)
    glossary: List[GlossaryItem] = Field(..., min_length=5, max_length=12)
    worked_examples: List[str] = Field(
        default_factory=list, max_length=4,
        description="Optional step-by-step worked examples for the hardest concepts.",
    )
    discussion_questions: List[str] = Field(..., min_length=4, max_length=8)
    further_reading: List[str] = Field(default_factory=list, max_length=6)


# ======================================================================
# FAQ
# ======================================================================

class FAQItem(BaseModel):
    question: str = Field(..., min_length=10)
    answer: str = Field(..., min_length=40)
    category: Optional[str] = None


class FAQ(BaseModel):
    title: str
    items: List[FAQItem] = Field(..., min_length=6, max_length=12)


# ======================================================================
# Research review (BLUF-style peer review)
# ======================================================================

class WhyWeCare(BaseModel):
    direct_techniques: List[str] = Field(..., min_length=2, max_length=5)
    cost_effectiveness: List[str] = Field(default_factory=list, max_length=3)
    novelty: List[str] = Field(default_factory=list, max_length=3)


class ResearchReview(BaseModel):
    title: str
    bluf: str = Field(
        ..., min_length=80,
        description=(
            "Brutally honest one-paragraph verdict. Start with an adjective "
            "(e.g. 'Interesting but approach with skepticism...'). Must name "
            "at least one strength and one weakness."
        ),
    )
    notable_authors: List[str] = Field(default_factory=list, max_length=8)
    affiliations: List[str] = Field(default_factory=list, max_length=6)
    short_take: str = Field(
        ..., min_length=200,
        description="3-6 sentences describing methodology and key result plainly.",
    )
    contribution_claim: str = Field(
        ..., description="What the authors say they contribute."
    )
    actual_contribution: str = Field(
        ...,
        description=(
            "What they actually demonstrate, net of weaknesses. Call out any "
            "gap between claimed and actual contribution."
        ),
    )
    why_we_care: WhyWeCare
    methodological_limitations: List[str] = Field(..., min_length=2, max_length=6)
    potential_applications: List[str] = Field(..., min_length=2, max_length=6)
    verdict: Literal["adopt", "pilot", "watch", "skip"] = Field(
        ..., description="Actionable verdict for the reading team."
    )
    confidence: Literal["high", "medium", "low"]
    resources: List[str] = Field(default_factory=list, max_length=6)


# ======================================================================
# Flashcards
# ======================================================================

class Flashcard(BaseModel):
    front: str = Field(..., min_length=5)
    back: str = Field(..., min_length=10)
    bloom_level: Literal[
        "remember", "understand", "apply", "analyze", "evaluate", "create"
    ] = Field(..., description="Cognitive level this card targets.")
    card_type: Literal["basic", "cloze", "reverse"] = "basic"
    tags: List[str] = Field(default_factory=list, max_length=5)


class Flashcards(BaseModel):
    title: str
    cards: List[Flashcard] = Field(..., min_length=10, max_length=20)

    @model_validator(mode="after")
    def _diverse_bloom(self) -> "Flashcards":
        levels = {c.bloom_level for c in self.cards}
        if len(levels) < 3:
            raise ValueError(
                "Flashcard deck must span at least 3 distinct Bloom levels."
            )
        return self


# ======================================================================
# Quiz
# ======================================================================

class QuizQuestion(BaseModel):
    question: str = Field(..., min_length=15)
    options: List[str] = Field(..., min_length=4, max_length=4)
    answer_index: int = Field(..., ge=0, le=3)
    explanation: str = Field(..., min_length=30)
    bloom_level: Literal[
        "remember", "understand", "apply", "analyze", "evaluate"
    ] = Field(..., description="Cognitive level this question targets.")
    difficulty: Literal["easy", "medium", "hard"]


class Quiz(BaseModel):
    title: str
    questions: List[QuizQuestion] = Field(..., min_length=5, max_length=12)

    @model_validator(mode="after")
    def _answer_in_range(self) -> "Quiz":
        for q in self.questions:
            if q.answer_index >= len(q.options):
                raise ValueError("answer_index out of range for options")
        return self


# ======================================================================
# Mind map
# ======================================================================

class MindMapNode(BaseModel):
    label: str = Field(..., min_length=2, max_length=60)
    children: List["MindMapNode"] = Field(default_factory=list, max_length=6)


MindMapNode.model_rebuild()


class MindMap(BaseModel):
    central_topic: str
    branches: List[MindMapNode] = Field(..., min_length=4, max_length=8)


# ======================================================================
# Timeline
# ======================================================================

class TimelineEvent(BaseModel):
    date: str = Field(..., description="ISO 8601 date or year, e.g. '2024-05' or '2017'.")
    event: str = Field(..., min_length=10)
    category: Optional[str] = None
    importance: Literal["major", "minor"] = "major"


class Timeline(BaseModel):
    title: str
    events: List[TimelineEvent] = Field(..., min_length=5, max_length=15)


# ======================================================================
# Infographic
# ======================================================================

class InfoStat(BaseModel):
    value: str = Field(..., description="Headline numeric, e.g. '82%' or '$4.8M'.")
    label: str = Field(..., min_length=3, max_length=40)
    caveat: Optional[str] = Field(None, max_length=120)


class InfoSection(BaseModel):
    heading: str = Field(..., min_length=3, max_length=50)
    text: str = Field(..., min_length=40, max_length=240)
    icon_hint: Optional[str] = Field(
        None, description="A single word icon cue, e.g. 'chart', 'shield', 'clock'."
    )


class Infographic(BaseModel):
    title: str = Field(..., min_length=5)
    subtitle: str = Field(..., min_length=10)
    lede: str = Field(
        ..., min_length=40,
        description="One-sentence lede shown prominently under the title.",
    )
    stats: List[InfoStat] = Field(..., min_length=3, max_length=4)
    sections: List[InfoSection] = Field(..., min_length=3, max_length=6)
    takeaway: str = Field(
        ..., min_length=30,
        description="One-line takeaway printed in the footer banner.",
    )
    color_theme: Literal["blue", "green", "orange", "mono", "violet"] = "blue"


# ======================================================================
# Slide deck
# ======================================================================

class SlidePlan(BaseModel):
    """Narrative-arc plan produced before slide content is drafted."""

    narrative_arc: Literal[
        "problem-solution", "chronological", "compare-contrast", "pyramid",
        "hero-journey", "scqa"
    ]
    slide_budget: int = Field(..., ge=6, le=16)
    sections: List[str] = Field(
        ..., min_length=3, max_length=7,
        description="Ordered section headers (e.g. 'Opening', 'Context', ...).",
    )
    goal: str
    key_message: str


class Slide(BaseModel):
    title: str = Field(..., min_length=3, max_length=80)
    bullets: List[str] = Field(..., min_length=2, max_length=5)
    notes: str = Field(
        ..., min_length=40,
        description="Presenter notes: what the speaker says out loud.",
    )
    slide_type: Literal[
        "title", "agenda", "section", "content", "stat", "quote", "closing"
    ] = "content"


class SlideDeck(BaseModel):
    title: str
    subtitle: str
    plan: SlidePlan
    slides: List[Slide] = Field(..., min_length=6, max_length=16)


# ======================================================================
# Pitch deck
# ======================================================================

class PitchDeck(BaseModel):
    title: str
    tagline: str = Field(..., min_length=10, max_length=120)
    slides: List[Slide] = Field(..., min_length=8, max_length=12)


# ======================================================================
# Paper figure
# ======================================================================

class ChartPoint(BaseModel):
    x: str
    y: float


class ChartSeries(BaseModel):
    name: str
    data: List[ChartPoint] = Field(..., min_length=2)


class PaperFigure(BaseModel):
    title: str
    chart_type: Literal["bar", "line", "scatter", "grouped_bar"]
    x_label: str
    y_label: str
    series: List[ChartSeries] = Field(..., min_length=1, max_length=6)
    caption: str = Field(..., min_length=50)
    highlight_series: Optional[str] = Field(
        None,
        description="Name of the series to highlight visually, if any.",
    )
