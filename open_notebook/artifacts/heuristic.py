"""Deterministic fallback extractor for artifact generation.

When no AI provider is configured (local dev, CI, or offline demos) every
artifact generator can still produce a structured, meaningful output by
calling into the functions here. The extractor uses lightweight text
analysis: sentence segmentation, keyword frequency, TF-ish ranking, date
detection, and template-driven structure synthesis.

The goal is NOT to replace an LLM; the goal is to keep the pipeline
end-to-end runnable and produce plausible, non-empty artifacts.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "is", "are",
    "was", "were", "be", "been", "being", "to", "of", "in", "on", "at",
    "for", "with", "by", "from", "as", "that", "this", "these", "those",
    "it", "its", "their", "there", "here", "they", "them", "he", "she",
    "we", "you", "your", "our", "not", "no", "so", "than", "into",
    "about", "can", "could", "should", "would", "will", "may", "might",
    "also", "do", "does", "did", "have", "has", "had", "more", "most",
    "some", "any", "all", "which", "who", "whom", "whose", "what", "how",
    "why", "when", "where", "between", "over", "under", "after", "before",
    "one", "two", "three", "because", "due", "while", "during", "per",
    "such", "only", "other", "each", "just", "like", "new", "same",
    "very", "both", "many", "few", "much", "less",
}


# ----------------------------------------------------------------------
# Low-level utilities
# ----------------------------------------------------------------------

def extract_input_block(prompt: str) -> str:
    """Pull the ``# INPUT`` section out of a structured prompt.

    Also strips per-source metadata header lines (``SOURCE:``, ``AUTHOR:``,
    ``DATE:``, ``URL:``) so the heuristic ranker does not treat them as
    sentences.
    """
    body = prompt.split("# INPUT", 1)[1].strip() if "# INPUT" in prompt else prompt.strip()
    cleaned_lines = []
    for line in body.splitlines():
        lstripped = line.lstrip()
        if any(
            lstripped.upper().startswith(prefix)
            for prefix in ("SOURCE:", "AUTHOR:", "DATE:", "URL:")
        ):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def split_sentences(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    pieces = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", text)
    return [p.strip() for p in pieces if p.strip()]


def tokenize(text: str) -> List[str]:
    return re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", text.lower())


def keywords(text: str, top_n: int = 8) -> List[str]:
    tokens = [t for t in tokenize(text) if t not in _STOPWORDS]
    if not tokens:
        return []
    counts = Counter(tokens)
    return [w for w, _ in counts.most_common(top_n)]


def rank_sentences(text: str, top_n: int = 5) -> List[str]:
    sentences = split_sentences(text)
    if len(sentences) <= top_n:
        return sentences
    kw = set(keywords(text, top_n=20))
    scored: List[Tuple[float, int, str]] = []
    for idx, sent in enumerate(sentences):
        tokens = [t for t in tokenize(sent) if t not in _STOPWORDS]
        if not tokens:
            continue
        hits = sum(1 for t in tokens if t in kw)
        score = hits / max(1, len(tokens))
        position_bonus = 0.15 if idx < 3 else 0.0
        length_penalty = 0.1 if len(tokens) < 6 else 0.0
        scored.append((score + position_bonus - length_penalty, idx, sent))
    scored.sort(key=lambda x: (-x[0], x[1]))
    picked = sorted(scored[:top_n], key=lambda x: x[1])
    return [s for _, _, s in picked]


def extract_title(text: str) -> str:
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        upper = line.upper()
        if upper.startswith(("SOURCE:", "AUTHOR:", "DATE:", "URL:")):
            continue
        low = line.lower()
        if low.startswith("title:"):
            return line.split(":", 1)[1].strip().rstrip(".")
        if 8 <= len(line) <= 160:
            return line.rstrip(".")
    sentences = split_sentences(text)
    if sentences:
        return sentences[0][:120]
    return "Untitled Artifact"


def extract_dates(text: str) -> List[Tuple[str, str]]:
    """Return ``(date_label, surrounding_sentence)`` pairs.

    Looks for years, ISO dates, and ``Month YYYY`` phrases.
    """
    sentences = split_sentences(text)
    patterns = [
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s*\d{4}\b",
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b",
        r"\b(?:19|20)\d{2}\b",
    ]
    compiled = [re.compile(p) for p in patterns]
    results: List[Tuple[str, str]] = []
    seen = set()
    for sent in sentences:
        spans = []
        for pat in compiled:
            for match in pat.finditer(sent):
                spans.append((match.start(), match.end(), match.group(0)))
        spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
        consumed: List[Tuple[int, int]] = []
        for start, end, label in spans:
            if any(s <= start < e for s, e in consumed):
                continue
            consumed.append((start, end))
            key = (label, sent[:40])
            if key in seen:
                continue
            seen.add(key)
            results.append((label, sent))
    return results


# ----------------------------------------------------------------------
# Top-level heuristic JSON builder
# ----------------------------------------------------------------------

def heuristic_json(
    prompt: str,
    schema_hint: Optional[Dict[str, Any]] = None,
    artifact_type: Optional[str] = None,
) -> Dict[str, Any]:
    body = extract_input_block(prompt)
    dispatchers = {
        "briefing": _briefing,
        "study_guide": _study_guide,
        "faq": _faq,
        "research_review": _research_review,
        "flashcards": _flashcards,
        "quiz": _quiz,
        "mindmap": _mindmap,
        "timeline": _timeline,
        "infographic": _infographic,
        "slide_deck": _slide_deck,
        "pitch_deck": _pitch_deck,
        "paper_figure": _paper_figure,
    }
    func = dispatchers.get(artifact_type or "", _generic)
    return func(body)


# ----------------------------------------------------------------------
# Per-artifact heuristics
# ----------------------------------------------------------------------

def _generic(text: str) -> Dict[str, Any]:
    return {
        "title": extract_title(text),
        "summary": " ".join(rank_sentences(text, top_n=3)),
        "keywords": keywords(text, 8),
        "bullets": rank_sentences(text, top_n=5),
    }


def _briefing(text: str) -> Dict[str, Any]:
    ranked = rank_sentences(text, top_n=6)
    bluf = ranked[0] if ranked else "Key finding pending review."
    return {
        "title": extract_title(text),
        "bluf": bluf,
        "audience": "General",
        "key_points": ranked[1:5] if len(ranked) > 1 else ranked,
        "supporting_details": ranked[5:] if len(ranked) > 5 else [],
        "action_items": [
            f"Review: {k}" for k in keywords(text, 3)
        ],
        "keywords": keywords(text, 8),
    }


def _study_guide(text: str) -> Dict[str, Any]:
    sents = rank_sentences(text, top_n=8)
    kws = keywords(text, 10)
    glossary = []
    for kw in kws[:6]:
        match = next((s for s in split_sentences(text) if kw in s.lower()), None)
        glossary.append({"term": kw, "definition": match or kw.capitalize()})
    return {
        "title": f"Study Guide: {extract_title(text)}",
        "overview": sents[0] if sents else "",
        "learning_objectives": [f"Understand {kw}" for kw in kws[:4]],
        "key_concepts": sents[1:5],
        "glossary": glossary,
        "discussion_questions": [
            f"What is the significance of {kw}?" for kw in kws[:4]
        ],
        "further_reading": [],
    }


def _faq(text: str) -> Dict[str, Any]:
    sents = rank_sentences(text, top_n=8)
    kws = keywords(text, 8)
    items = []
    for kw, sent in zip(kws, sents):
        items.append(
            {
                "question": f"What does this material say about {kw}?",
                "answer": sent,
            }
        )
    if not items:
        items = [{"question": "What is the main point?", "answer": " ".join(sents[:2])}]
    return {
        "title": f"FAQ: {extract_title(text)}",
        "items": items,
    }


def _research_review(text: str) -> Dict[str, Any]:
    sents = rank_sentences(text, top_n=10)
    kws = keywords(text, 10)
    return {
        "title": extract_title(text),
        "bluf": sents[0] if sents else "",
        "notable_authors": [],
        "affiliations": [],
        "short_take": " ".join(sents[:3]),
        "why_we_care": {
            "direct_techniques": sents[3:6] or sents[:3],
            "cost_effectiveness": sents[6:7] or [],
        },
        "limitations": sents[7:9] or [],
        "potential_applications": [f"Applications to {kw}" for kw in kws[:4]],
        "resources": [],
        "keywords": kws,
    }


def _flashcards(text: str) -> Dict[str, Any]:
    sents = rank_sentences(text, top_n=10)
    kws = keywords(text, 10)
    cards = []
    for kw, sent in zip(kws, sents):
        cards.append(
            {
                "front": f"Define or explain: {kw}",
                "back": sent,
                "tags": [kw],
            }
        )
    return {
        "title": f"Flashcards: {extract_title(text)}",
        "cards": cards or [
            {"front": "Main idea", "back": sents[0] if sents else "", "tags": []}
        ],
    }


def _quiz(text: str) -> Dict[str, Any]:
    sents = rank_sentences(text, top_n=8)
    kws = keywords(text, 10)
    questions = []
    for idx, (kw, sent) in enumerate(zip(kws, sents)):
        distractors = [f"An alternative view on {alt}" for alt in kws if alt != kw][:3]
        while len(distractors) < 3:
            distractors.append("Not covered in sources")
        options = [sent] + distractors
        questions.append(
            {
                "question": f"Which statement best describes the role of '{kw}'?",
                "options": options,
                "answer_index": 0,
                "explanation": sent,
            }
        )
    if not questions:
        questions.append(
            {
                "question": "What is the primary focus of this material?",
                "options": [
                    " ".join(sents[:1]) or "Unknown",
                    "An unrelated topic",
                    "Pure fiction",
                    "Historical trivia",
                ],
                "answer_index": 0,
                "explanation": "Derived from the source summary.",
            }
        )
    return {
        "title": f"Quiz: {extract_title(text)}",
        "questions": questions,
    }


def _mindmap(text: str) -> Dict[str, Any]:
    kws = keywords(text, 12)
    central = extract_title(text)
    branches = []
    for kw in kws[:6]:
        match = next((s for s in split_sentences(text) if kw in s.lower()), "")
        branches.append(
            {
                "label": kw.title(),
                "children": [match[:120]] if match else [],
            }
        )
    return {
        "central_topic": central,
        "branches": branches or [{"label": "Main Topic", "children": []}],
    }


def _timeline(text: str) -> Dict[str, Any]:
    pairs = extract_dates(text)
    events = []
    for label, sent in pairs[:10]:
        events.append({"date": label, "event": sent[:200]})
    if not events:
        sents = rank_sentences(text, top_n=4)
        today = datetime.now(timezone.utc).year
        for i, sent in enumerate(sents):
            events.append({"date": str(today - i), "event": sent})
    return {
        "title": f"Timeline: {extract_title(text)}",
        "events": events,
    }


def _infographic(text: str) -> Dict[str, Any]:
    sents = rank_sentences(text, top_n=6)
    kws = keywords(text, 6)
    stats = []
    for m in re.finditer(
        r"([\d,.]+\s?(?:%|percent|M|B|K|million|billion|thousand)?)"
        r"\s+([A-Za-z][A-Za-z\s\-]{2,30})",
        text,
    ):
        stats.append({"value": m.group(1).strip(), "label": m.group(2).strip()})
        if len(stats) >= 4:
            break
    while len(stats) < 3:
        stats.append({"value": str(len(kws)), "label": "key topics"})
    return {
        "title": extract_title(text),
        "subtitle": sents[0] if sents else "",
        "sections": [
            {"heading": kw.title(), "text": s}
            for kw, s in zip(kws, sents)
        ],
        "stats": stats[:4],
        "color_theme": "blue",
    }


def _slide_deck(text: str) -> Dict[str, Any]:
    sents = rank_sentences(text, top_n=12)
    kws = keywords(text, 8)
    slides = [
        {
            "title": extract_title(text),
            "bullets": [sents[0] if sents else ""],
            "notes": "Opening slide.",
        }
    ]
    for i in range(0, min(len(kws), 6)):
        slides.append(
            {
                "title": kws[i].title(),
                "bullets": [
                    s for s in sents[i * 2 : i * 2 + 3] if s
                ]
                or ["Details to expand"],
                "notes": sents[i] if i < len(sents) else "",
            }
        )
    slides.append(
        {
            "title": "Conclusion",
            "bullets": rank_sentences(text, top_n=3),
            "notes": "Summary slide.",
        }
    )
    return {
        "title": extract_title(text),
        "subtitle": "Auto-generated from sources",
        "slides": slides,
    }


def _pitch_deck(text: str) -> Dict[str, Any]:
    sents = rank_sentences(text, top_n=12)
    title = extract_title(text)
    section = lambda t, b: {"title": t, "bullets": b or ["TBD"]}  # noqa: E731
    return {
        "title": title,
        "tagline": sents[0] if sents else "",
        "slides": [
            section("Cover", [title, "An auto-generated investor briefing"]),
            section("Problem", sents[1:3]),
            section("Solution", sents[3:5]),
            section("Market", sents[5:6] or ["Market sizing pending"]),
            section("Product", sents[6:8]),
            section("Traction", sents[8:9] or ["Early traction signals"]),
            section("Team", ["Details TBD"]),
            section("Ask", ["Investment ask: TBD"]),
        ],
    }


def _paper_figure(text: str) -> Dict[str, Any]:
    """Fallback: present three methods with synthetic scores."""
    kws = keywords(text, 3) or ["method_a", "method_b", "method_c"]
    return {
        "title": f"Figure: Comparison of {', '.join(kws)}",
        "chart_type": "bar",
        "x_label": "Approach",
        "y_label": "Score",
        "series": [
            {
                "name": "Primary",
                "data": [
                    {"x": kws[0], "y": 0.72},
                    {"x": kws[1] if len(kws) > 1 else "b", "y": 0.81},
                    {"x": kws[2] if len(kws) > 2 else "c", "y": 0.69},
                ],
            }
        ],
        "caption": "Heuristic placeholder figure; replace with LLM-driven data when available.",
    }
