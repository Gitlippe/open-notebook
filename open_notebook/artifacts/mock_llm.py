"""StructuredMockChat: an offline ``StructuredChat`` implementation.

The critical property: this mock implements the *same protocol* as the
real LLM backend and returns real Pydantic objects that validate against
the artifact schemas. It is not a shortcut around the workflow — every
generator runs the identical code path (extract claims → draft → critique
→ refine) when backed by this mock.

The mock composes its outputs from:

1. **Extractive analysis** of the source text (sentence ranking, entity
   and number extraction, date parsing, keyword TF scoring).
2. **Schema-driven templating** — it inspects the requested Pydantic
   schema and fills each field using type/field-name heuristics combined
   with the extracted material.
3. **Critique awareness** — when asked for a ``Critique`` object, it
   *actually* compares the draft against the source material and flags
   missing claims, near-duplicate bullets, and undersized sections.

This is not "heuristic output pretending to be an LLM" — it is a
deterministic structured-output engine that exercises the same workflow
as a real LLM. Tests, demos, and first-run UX all benefit.
"""
from __future__ import annotations

import re
from collections import Counter
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar

from pydantic import BaseModel

from open_notebook.artifacts import schemas as S

T = TypeVar("T", bound=BaseModel)


# ----------------------------------------------------------------------
# Text analysis utilities
# ----------------------------------------------------------------------

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "is", "are", "was",
    "were", "be", "been", "being", "to", "of", "in", "on", "at", "for",
    "with", "by", "from", "as", "that", "this", "these", "those", "it",
    "its", "their", "there", "here", "they", "them", "we", "you", "your",
    "our", "not", "no", "so", "than", "into", "about", "can", "could",
    "should", "would", "will", "may", "might", "also", "do", "does", "did",
    "have", "has", "had", "more", "most", "some", "any", "all", "which",
    "who", "whom", "whose", "what", "how", "why", "when", "where", "over",
    "under", "after", "before", "one", "two", "three", "because", "due",
    "while", "during", "per", "such", "only", "other", "each", "just",
    "like", "new", "same", "very", "both", "many", "few", "much", "less",
    "between",
}


class _Analysis:
    def __init__(self, text: str) -> None:
        self.raw = text
        self.clean = self._clean(text)
        self.sentences = self._sentences(self.clean)
        self.tokens = self._tokens(self.clean)
        self.kw = self._keywords(self.tokens)
        self.numbers = self._numbers(text)
        self.dates = self._dates(text)
        self.entities = self._entities(text)
        self.title = self._title(text)

    @staticmethod
    def _clean(text: str) -> str:
        """Strip metadata/preamble lines so ranking sees real content only.

        Handles both raw-source headers (``SOURCE:``, ``AUTHOR:``, …) and
        the structured-context block emitted by
        :func:`open_notebook.artifacts.workflow.claims_to_context`.
        """
        lines: List[str] = []
        in_claims_block = False
        in_bullet_block = False  # used for NUMERIC FACTS: / NAMED ENTITIES: blocks
        skip_prefixes = (
            "SOURCE:", "AUTHOR:", "AUTHORS:", "URL:", "DATE:",
            "AFFILIATIONS:", "AFFILIATION:", "PUBLISHED:", "DOI:",
            "AUDIENCE:", "DEPTH:", "TOPIC:", "PURPOSE:",
            "ORIGINAL AUDIENCE:",
        )
        bullet_block_prefixes = ("NUMERIC FACTS:", "NAMED ENTITIES:")
        for raw in text.splitlines():
            stripped = raw.lstrip()
            up = stripped.upper()
            if up.startswith("EXTRACTED CLAIMS:"):
                in_claims_block = True
                in_bullet_block = False
                continue
            if any(up.startswith(p) for p in bullet_block_prefixes):
                in_claims_block = False
                in_bullet_block = True
                continue
            if in_bullet_block:
                if not stripped:
                    in_bullet_block = False
                    lines.append(raw)
                    continue
                if stripped.startswith("-"):
                    continue
                # Regular content → exit block
                in_bullet_block = False
            if in_claims_block:
                # Claim block format: "  N. [importance/cat] text" followed by
                # "     evidence: ..." — we want the text, drop everything else.
                m = re.match(
                    r"\s*\d+\.\s*\[[^\]]+\]\s*(.+)", raw,
                )
                if m:
                    text = m.group(1).rstrip()
                    if not text.endswith((".", "!", "?")):
                        text += "."
                    lines.append(text)
                    continue
                if stripped.lower().startswith("evidence:"):
                    continue
                if stripped.startswith("-"):
                    # Numeric fact / named entity bullets: drop
                    continue
                if not stripped:
                    in_claims_block = False
                    lines.append(raw)
                    continue
                in_claims_block = False
            if any(up.startswith(p) for p in skip_prefixes):
                continue
            lines.append(raw)
        return "\n".join(lines).strip()

    @staticmethod
    def _sentences(text: str) -> List[str]:
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return []
        pieces = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", text)
        return [p.strip() for p in pieces if p.strip() and len(p.split()) > 3]

    @staticmethod
    def _tokens(text: str) -> List[str]:
        return re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", text.lower())

    def _keywords(self, tokens: List[str], top: int = 30) -> List[str]:
        filtered = [t for t in tokens if t not in _STOPWORDS and len(t) > 3]
        if not filtered:
            return []
        counts = Counter(filtered)
        return [w for w, _ in counts.most_common(top)]

    @staticmethod
    def _numbers(text: str) -> List[str]:
        out: List[str] = []
        for m in re.finditer(
            r"(?:\$\s?\d[\d,.]*\s?(?:[MBK]|million|billion|thousand)?|"
            r"\d+(?:\.\d+)?\s?%|"
            r"\d+(?:\.\d+)?x|"
            r"\d{1,3}(?:,\d{3})+|"
            r"\d+(?:\.\d+)?\s?(?:hours?|minutes?|days?|weeks?|months?|years?))",
            text,
        ):
            out.append(m.group(0).strip())
        return list(dict.fromkeys(out))[:20]

    @staticmethod
    def _dates(text: str) -> List[Tuple[str, str]]:
        patterns = [
            r"\b\d{4}-\d{2}-\d{2}\b",
            r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s*\d{4}\b",
            r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b",
            r"\b(?:Q[1-4]\s+)?(?:19|20)\d{2}\b",
        ]
        sentences = _Analysis._sentences(text)
        out: List[Tuple[str, str]] = []
        seen = set()
        for sent in sentences:
            spans = []
            for pat in patterns:
                for m in re.finditer(pat, sent):
                    spans.append((m.start(), m.end(), m.group(0)))
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
                out.append((label, sent))
        return out

    @staticmethod
    def _entities(text: str) -> List[str]:
        entities: List[str] = []
        for m in re.finditer(
            r"\b([A-Z][a-zA-Z]{2,}(?:\s+[A-Z][a-zA-Z]{2,}){0,3})\b",
            text,
        ):
            token = m.group(1)
            if token.split()[0].lower() in {
                "the", "this", "that", "in", "on", "at", "for", "and",
                "but", "he", "she", "they", "we", "i",
            }:
                continue
            entities.append(token)
        out = []
        seen = set()
        for e in entities:
            if e not in seen and len(e) > 3:
                seen.add(e)
                out.append(e)
            if len(out) >= 20:
                break
        return out

    @staticmethod
    def _title(text: str) -> str:
        # Topic line emitted by claims_to_context() is the best signal.
        for raw in text.splitlines():
            line = raw.strip()
            if line.upper().startswith("TOPIC:"):
                return line.split(":", 1)[1].strip().rstrip(".")[:160]
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            up = line.upper()
            if up.startswith((
                "SOURCE:", "AUTHOR:", "AUTHORS:", "DATE:", "URL:", "PURPOSE:",
                "ORIGINAL AUDIENCE:", "EXTRACTED CLAIMS:", "NUMERIC FACTS:",
                "NAMED ENTITIES:", "AUDIENCE:", "DEPTH:", "AFFILIATIONS:",
                "AFFILIATION:", "PUBLISHED:", "DOI:",
            )):
                continue
            if line.startswith(("-", "*", "•")) or line[0].isdigit() and ("." in line[:4]):
                continue
            low = line.lower()
            if low.startswith("title:"):
                return line.split(":", 1)[1].strip().rstrip(".")
            if 8 <= len(line) <= 160:
                return line.rstrip(".")
        sents = _Analysis._sentences(text)
        return (sents[0] if sents else "Untitled")[:120]

    def rank(self, n: int, *, min_words: int = 5) -> List[str]:
        if not self.sentences:
            return []
        kw = set(self.kw[:25])
        scored = []
        for idx, sent in enumerate(self.sentences):
            tokens = [t for t in re.findall(r"\w+", sent.lower())
                      if t not in _STOPWORDS]
            if len(tokens) < min_words:
                continue
            hits = sum(1 for t in tokens if t in kw)
            score = hits / max(1, len(tokens))
            score += 0.15 if idx < 3 else 0.0
            score += 0.2 if any(n in sent for n in self.numbers) else 0.0
            scored.append((score, idx, sent))
        scored.sort(key=lambda x: (-x[0], x[1]))
        picked = sorted(scored[:n], key=lambda x: x[1])
        return [s for _, _, s in picked]

    def sentences_mentioning(self, term: str) -> List[str]:
        low = term.lower()
        return [s for s in self.sentences if low in s.lower()]


# ----------------------------------------------------------------------
# Schema-driven composer
# ----------------------------------------------------------------------

class StructuredMockChat:
    """Offline ``StructuredChat`` that fabricates structurally-valid outputs.

    It looks at the requested ``schema`` and dispatches to a composer that
    understands that schema. Uses :class:`_Analysis` for the heavy lifting.
    """

    async def astructured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: Type[T],
        temperature: float = 0.1,
    ) -> T:
        analysis = _Analysis(user_prompt)
        hint = (system_prompt + "\n" + user_prompt).lower()
        data = self._compose(schema, analysis, hint, user_prompt)
        return schema.model_validate(data)

    async def atext(self, *, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> str:
        analysis = _Analysis(user_prompt)
        return " ".join(analysis.rank(3)) or analysis.title

    # ------------------------------------------------------------------
    def _compose(
        self,
        schema: Type[BaseModel],
        analysis: _Analysis,
        hint: str,
        raw: str,
    ) -> Dict[str, Any]:
        dispatch = {
            S.ClaimSet: self._claim_set,
            S.Critique: self._critique,
            S.Briefing: self._briefing,
            S.StudyGuide: self._study_guide,
            S.FAQ: self._faq,
            S.ResearchReview: self._research_review,
            S.Flashcards: self._flashcards,
            S.Quiz: self._quiz,
            S.MindMap: self._mindmap,
            S.Timeline: self._timeline,
            S.Infographic: self._infographic,
            S.SlideDeck: self._slide_deck,
            S.PitchDeck: self._pitch_deck,
            S.PaperFigure: self._paper_figure,
        }
        fn = dispatch.get(schema)
        if fn is None:
            return {}
        return fn(analysis, hint, raw)

    # ------------------------------------------------------------------
    # Individual composers
    # ------------------------------------------------------------------

    def _claim_set(self, a: _Analysis, hint: str, raw: str) -> Dict[str, Any]:
        ranked = a.rank(14, min_words=6) or a.sentences[:14]
        claims = []
        categories = ["result", "methodology", "limitation", "market",
                      "metric", "context", "claim"]
        for i, sent in enumerate(ranked):
            importance = "critical" if i < 2 else (
                "high" if i < 6 else ("medium" if i < 10 else "low")
            )
            numeric_hit = any(n in sent for n in a.numbers)
            category = "metric" if numeric_hit else categories[i % len(categories)]
            evidence = sent[:200]
            claims.append(
                {
                    "text": sent.rstrip("."),
                    "evidence": evidence,
                    "importance": importance,
                    "category": category,
                }
            )
        while len(claims) < 5:
            claims.append(
                {
                    "text": a.title,
                    "evidence": a.title,
                    "importance": "low",
                    "category": "context",
                }
            )
        return {
            "topic": a.title,
            "purpose": _derive_purpose(a, hint),
            "audience_hint": _derive_audience(a, hint),
            "claims": claims,
            "numeric_facts": a.numbers[:10],
            "named_entities": a.entities[:15],
        }

    def _critique(self, a: _Analysis, hint: str, raw: str) -> Dict[str, Any]:
        draft_json = _find_json_block(raw, "DRAFT ARTIFACT") or \
            _find_json_block(raw, "CURRENT DRAFT")
        context_block = _find_block(raw, "SOURCE CONTEXT")
        issues: List[str] = []
        missing: List[str] = []
        redundancies: List[str] = []
        suggested: List[str] = []

        if draft_json and context_block:
            context_sents = _Analysis(context_block).rank(12, min_words=5)
            draft_bullets = _collect_bullets(draft_json)
            # Missing: important source sentence not present in draft text
            draft_text = " ".join(draft_bullets).lower()
            for sent in context_sents[:8]:
                tokens = {
                    t for t in re.findall(r"\w+", sent.lower())
                    if t not in _STOPWORDS and len(t) > 4
                }
                if not tokens:
                    continue
                overlap = sum(1 for t in tokens if t in draft_text)
                if overlap / max(1, len(tokens)) < 0.35:
                    missing.append(sent[:180])
                if len(missing) >= 3:
                    break
            # Redundancies
            for i in range(len(draft_bullets)):
                for j in range(i + 1, len(draft_bullets)):
                    ratio = SequenceMatcher(
                        None, draft_bullets[i].lower(), draft_bullets[j].lower()
                    ).ratio()
                    if ratio > 0.8:
                        redundancies.append(
                            f"Bullets are near-duplicates: "
                            f"'{draft_bullets[i][:60]}' vs '{draft_bullets[j][:60]}'"
                        )
                        break
                if redundancies:
                    break
            # Short bullets
            for b in draft_bullets:
                if len(b.split()) < 4:
                    issues.append(f"Bullet too short to be substantive: '{b}'")
                    break

            if missing:
                suggested.append(
                    "Incorporate the missing source facts listed above."
                )
            if redundancies:
                suggested.append("Consolidate near-duplicate bullets.")
        if not issues and not missing and not redundancies:
            quality = 8
        else:
            quality = max(4, 9 - len(issues) - len(missing) - len(redundancies))
        return {
            "issues": issues,
            "missing": missing,
            "redundancies": redundancies,
            "suggested_edits": suggested,
            "quality_score": quality,
        }

    def _briefing(self, a: _Analysis, hint: str, raw: str) -> Dict[str, Any]:
        ranked = a.rank(8, min_words=7) or a.sentences
        numeric_sents = [s for s in a.sentences if any(n in s for n in a.numbers)]
        risk_sents = [s for s in a.sentences
                      if any(k in s.lower() for k in
                             ["risk", "concern", "flagged", "however", "but "])]
        audience = _extract_audience_hint(hint)
        bluf = ranked[0] if ranked else a.title
        if len(bluf) < 60 and len(a.sentences) > 0:
            bluf = (bluf + " " + a.sentences[0]).strip()
        key_points = ranked[1:6] or ranked
        supporting = (numeric_sents or ranked[6:])[:4] or ranked[:2]
        risks = risk_sents[:3]
        actions = _derive_actions(a)
        return {
            "title": a.title[:110],
            "audience": audience,
            "bluf": _ensure_min_len(bluf, 60, a),
            "key_points": _topup(key_points, 3, ranked + a.sentences)[:6],
            "supporting_details": _topup(supporting, 2, numeric_sents + ranked)[:5],
            "action_items": _topup(actions, 2, _default_actions(a))[:5],
            "risks": risks[:4],
            "keywords": (a.kw[:8] or ["summary"])[:10],
        }

    def _study_guide(self, a: _Analysis, hint: str, raw: str) -> Dict[str, Any]:
        ranked = a.rank(10, min_words=5) or a.rank(10, min_words=3) or a.sentences
        concepts = ranked[:8] or a.sentences[:8]
        while len(concepts) < 5:
            concepts.append(f"Key concept: {a.kw[len(concepts) % max(1, len(a.kw))] if a.kw else 'core idea'}")
        kws = a.kw[:10] or ["concept", "principle", "context", "application", "limitation"]
        bloom_cycle = ["understand", "understand", "apply", "analyze", "evaluate", "create"]
        objectives = [
            {
                "bloom_level": bloom_cycle[i % len(bloom_cycle)],
                "statement": _objective_verb(bloom_cycle[i % len(bloom_cycle)])
                + " " + kw + " and its role in this material.",
            }
            for i, kw in enumerate(kws[:5])
        ]
        glossary = []
        for kw in kws[:8]:
            sentences = a.sentences_mentioning(kw)
            definition = (sentences[0] if sentences else f"A core concept: {kw}.")[:220]
            if len(definition) < 20:
                definition = f"Key concept referenced throughout the material: {kw}."
            glossary.append({"term": kw, "definition": definition})
        while len(glossary) < 5:
            filler_term = f"term_{len(glossary)+1}"
            glossary.append({
                "term": filler_term,
                "definition": f"Placeholder definition for {filler_term} pending further content.",
            })
        worked = [s for s in a.sentences
                  if any(k in s.lower() for k in ["example", "for instance",
                                                  "step", "procedure", "process"])][:3]
        discussion = [
            f"How does {kw} influence the overall argument?" for kw in kws[:5]
        ]
        while len(discussion) < 4:
            discussion.append(
                f"What unresolved questions remain about {kws[len(discussion) % len(kws)]}?"
            )
        return {
            "title": f"Study Guide: {a.title}",
            "overview": _ensure_min_len(" ".join(ranked[:3]), 120, a),
            "prerequisites": kws[5:8][:5],
            "learning_objectives": _topup_obj(objectives, 4, bloom_cycle, kws)[:8],
            "key_concepts": concepts[:10],
            "glossary": glossary[:12],
            "worked_examples": worked[:4],
            "discussion_questions": discussion[:8] if len(discussion) >= 4 else (discussion + [f"What did you take away about {kw}?" for kw in kws[:4]])[:8],
            "further_reading": [],
        }

    def _faq(self, a: _Analysis, hint: str, raw: str) -> Dict[str, Any]:
        ranked = a.rank(12)
        kws = a.kw[:12]
        items = []
        q_frames = [
            "What does this material say about {}?",
            "Why is {} important here?",
            "How is {} described in the source?",
            "What are the key details about {}?",
            "What role does {} play?",
            "What should readers know about {}?",
        ]
        for i, kw in enumerate(kws[:10]):
            ctx = a.sentences_mentioning(kw)
            answer = ctx[0] if ctx else (ranked[i] if i < len(ranked) else a.title)
            question = q_frames[i % len(q_frames)].format(kw)
            items.append({
                "question": question,
                "answer": _ensure_min_len(answer, 60, a),
                "category": "overview" if i < 3 else "details",
            })
        return {"title": f"FAQ: {a.title}", "items": items[:10] or [
            {"question": f"What is this about?", "answer": _ensure_min_len(" ".join(ranked[:2]), 60, a)}
            for _ in range(6)
        ]}

    def _research_review(self, a: _Analysis, hint: str, raw: str) -> Dict[str, Any]:
        ranked = a.rank(12)
        weak = [s for s in a.sentences
                if any(k in s.lower() for k in
                       ["never", "limitation", "however", "flaw", "but ",
                        "unclear", "fail", "weakness", "missing"])]
        strong = [s for s in a.sentences
                  if any(k in s.lower() for k in
                         ["improve", "increase", "better", "outperform",
                          "novel", "propose"])]
        numeric_sents = [s for s in a.sentences if any(n in s for n in a.numbers)]
        verdict = "watch"
        if weak and strong:
            verdict = "pilot"
        elif strong and not weak:
            verdict = "adopt"
        elif weak and not strong:
            verdict = "skip"
        return {
            "title": f"Research Review: {a.title}",
            "bluf": _ensure_min_len(
                (f"Interesting but approach with skepticism. "
                 f"{strong[0] if strong else ranked[0] if ranked else a.title} "
                 f"However {weak[0] if weak else 'the evidence is limited.'}"),
                120, a,
            ),
            "notable_authors": [
                e for e in a.entities
                if " " in e and not any(k in e.upper() for k in (
                    "ORIGINAL AUDIENCE", "EXTRACTED CLAIMS", "NUMERIC FACTS",
                    "NAMED ENTITIES", "AUDIENCE", "CLAIMS", "FACTS", "DATE",
                    "AUTHOR", "SOURCE", "AFFILIATION", "URL"))
            ][:4],
            "affiliations": [
                e for e in a.entities
                if any(k in e.lower() for k in (
                    "university", "lab", "inc", "corp", "institute"))
            ][:3],
            "short_take": _ensure_min_len(" ".join(ranked[:4]), 220, a),
            "contribution_claim": strong[0] if strong else ranked[0] if ranked else a.title,
            "actual_contribution": (
                (strong[0] if strong else "Incremental improvement on existing methods.") +
                (" " + weak[0] if weak else "")
            ),
            "why_we_care": {
                "direct_techniques": _topup(numeric_sents[:3] or ranked[:3], 2, [
                    "Concrete techniques could be adopted directly.",
                    "The method is straightforward to reproduce.",
                ]),
                "cost_effectiveness": [s for s in numeric_sents
                                       if any(k in s.lower() for k in ["cost", "$", "cheaper"])][:3],
                "novelty": strong[:3],
            },
            "methodological_limitations": _topup(weak[:4], 2, [
                "Evaluation scope may be limited to the reported benchmarks.",
                "Reproducibility details are not fully specified.",
            ]),
            "potential_applications": _topup(
                [
                    f"Pilot the approach on {a.kw[0] if a.kw else 'a small domain'} "
                    f"before broader rollout.",
                    f"Compare results head-to-head against the current baseline "
                    f"{'on ' + a.kw[1] if len(a.kw) > 1 else 'in a controlled evaluation'}.",
                    f"Evaluate cost and latency impact under production traffic.",
                ],
                2,
                [
                    "Feasibility study for production deployment.",
                    "Shadow-mode deployment for quality comparison.",
                ],
            )[:5],
            "verdict": verdict,
            "confidence": "medium",
            "resources": [],
        }

    def _flashcards(self, a: _Analysis, hint: str, raw: str) -> Dict[str, Any]:
        kws = a.kw[:12] or ["topic"]
        ranked = a.rank(16)
        levels = ["remember", "understand", "apply", "analyze", "evaluate", "create"]
        cards = []
        for i, kw in enumerate(kws[:10]):
            mentions = a.sentences_mentioning(kw)
            back = mentions[0] if mentions else (ranked[i] if i < len(ranked) else a.title)
            level = levels[i % len(levels)]
            if level == "apply":
                front = f"Give a real-world scenario where {kw} would apply."
            elif level == "analyze":
                front = f"How does {kw} relate to other concepts in this material?"
            elif level == "evaluate":
                front = f"What are the strengths and weaknesses of {kw}?"
            elif level == "create":
                front = f"Outline a new use case that extends {kw}."
            elif level == "understand":
                front = f"Explain {kw} in your own words."
            else:
                front = f"Define: {kw}"
            cards.append({
                "front": front,
                "back": _ensure_min_len(back, 40, a),
                "bloom_level": level,
                "card_type": "basic",
                "tags": [kw],
            })
        # Ensure schema's diversity validator passes (≥3 distinct Bloom levels).
        while len(cards) < 10:
            cards.append({
                "front": f"Review: {a.title}",
                "back": _ensure_min_len(ranked[0] if ranked else a.title, 40, a),
                "bloom_level": levels[len(cards) % len(levels)],
                "card_type": "basic",
                "tags": [],
            })
        return {"title": f"Flashcards: {a.title}", "cards": cards[:15]}

    def _quiz(self, a: _Analysis, hint: str, raw: str) -> Dict[str, Any]:
        ranked = a.rank(8)
        kws = a.kw[:10] or ["topic"]
        levels = ["remember", "understand", "apply", "analyze", "evaluate"]
        difficulty_cycle = ["easy", "medium", "hard", "medium", "easy", "hard"]
        questions = []
        for i, kw in enumerate(kws[:6]):
            correct = (a.sentences_mentioning(kw) + ranked)[0] if (a.sentences_mentioning(kw) or ranked) else a.title
            distractors = [
                f"{other.capitalize()} plays no role in the material." for other in kws if other != kw
            ][:3]
            while len(distractors) < 3:
                distractors.append("Not covered in the sources.")
            # Order: correct first then distractors; we'll shuffle deterministically.
            options = [correct[:140]] + distractors
            # Place correct at position i % 4
            pos = i % 4
            options[0], options[pos] = options[pos], options[0]
            questions.append({
                "question": f"Which statement best describes the role of '{kw}'?",
                "options": options,
                "answer_index": pos,
                "explanation": _ensure_min_len(correct, 40, a),
                "bloom_level": levels[i % len(levels)],
                "difficulty": difficulty_cycle[i % len(difficulty_cycle)],
            })
        while len(questions) < 5:
            questions.append(questions[-1])
        return {"title": f"Quiz: {a.title}", "questions": questions[:8]}

    def _mindmap(self, a: _Analysis, hint: str, raw: str) -> Dict[str, Any]:
        kws = a.kw[:12] or ["topic"]
        branches = []
        for kw in kws[:6]:
            mentions = a.sentences_mentioning(kw)[:3]
            children = [{"label": _short(s, 50), "children": []} for s in mentions]
            branches.append({"label": kw.title(), "children": children})
        while len(branches) < 4:
            branches.append({"label": f"Area {len(branches)+1}", "children": []})
        return {"central_topic": a.title[:80], "branches": branches[:6]}

    def _timeline(self, a: _Analysis, hint: str, raw: str) -> Dict[str, Any]:
        events = []
        for label, sent in a.dates[:12]:
            category = None
            low = sent.lower()
            if any(k in low for k in ["release", "launch", "publish"]):
                category = "release"
            elif any(k in low for k in ["raise", "fund", "acquire"]):
                category = "business"
            events.append({
                "date": _canonicalize_date(label),
                "event": _short(sent, 200),
                "category": category,
                "importance": "major",
            })
        if len(events) < 5:
            # Pad with ordered synthetic years derived from ranked sentences
            # so the schema (min_length=5) is satisfied for short inputs.
            from datetime import datetime, timezone
            year = datetime.now(timezone.utc).year
            ranked = a.rank(8) or [a.title]
            i = 0
            existing_dates = {e["date"] for e in events}
            while len(events) < 5 and i < 20:
                sent = ranked[i % len(ranked)]
                candidate = str(year - (20 - i))
                if candidate not in existing_dates:
                    existing_dates.add(candidate)
                    events.append({
                        "date": candidate,
                        "event": _short(sent, 200),
                        "category": None,
                        "importance": "minor",
                    })
                i += 1
        events.sort(key=lambda e: e["date"])
        return {"title": f"Timeline: {a.title}", "events": events[:12]}

    def _infographic(self, a: _Analysis, hint: str, raw: str) -> Dict[str, Any]:
        ranked = a.rank(6)
        stats = []
        numeric_sents = [s for s in a.sentences if any(n in s for n in a.numbers)]
        for num in a.numbers[:4]:
            for sent in numeric_sents:
                if num in sent:
                    # Extract a short label: words around the number in the sentence.
                    label = re.sub(
                        r"\s+", " ",
                        re.sub(re.escape(num), "", sent)
                    ).strip()
                    label = _short(label, 38) or "metric"
                    stats.append({"value": num, "label": label})
                    break
        while len(stats) < 3:
            stats.append({"value": str(len(a.kw)), "label": "topics discussed"})

        kws = a.kw[:6] or ["topic"]
        sections = []
        for kw in kws[:4]:
            body_sents = a.sentences_mentioning(kw)
            body = body_sents[0] if body_sents else (ranked[0] if ranked else a.title)
            sections.append({
                "heading": kw.title(),
                "text": _ensure_min_len(_short(body, 220), 50, a),
                "icon_hint": _icon_for(kw),
            })
        while len(sections) < 3:
            sections.append({
                "heading": f"Point {len(sections)+1}",
                "text": _ensure_min_len(ranked[len(sections) % max(1, len(ranked))] if ranked else a.title, 50, a),
                "icon_hint": "chart",
            })

        # Decide theme by keyword vibe
        low = " ".join(a.kw[:10]).lower()
        if any(k in low for k in ["growth", "community", "open", "green"]):
            theme = "green"
        elif any(k in low for k in ["security", "risk", "threat"]):
            theme = "orange"
        elif any(k in low for k in ["research", "data", "report"]):
            theme = "violet"
        else:
            theme = "blue"

        return {
            "title": a.title[:80],
            "subtitle": _short(ranked[0] if ranked else a.title, 90),
            "lede": _ensure_min_len(ranked[0] if ranked else a.title, 50, a),
            "stats": stats[:4],
            "sections": sections[:5],
            "takeaway": _ensure_min_len(ranked[-1] if ranked else a.title, 40, a),
            "color_theme": theme,
        }

    def _slide_deck(self, a: _Analysis, hint: str, raw: str) -> Dict[str, Any]:
        ranked = a.rank(14)
        kws = a.kw[:6] or ["topic"]
        numeric_sents = [s for s in a.sentences if any(n in s for n in a.numbers)]
        arc = "scqa" if len(numeric_sents) >= 2 else "pyramid"

        def safe_slide(title: str, bullets: List[str], notes: str, slide_type: str) -> Dict[str, Any]:
            cleaned = [_short(b, 120) for b in bullets if b][:5]
            pool_idx = 0
            while len(cleaned) < 2:
                filler = ranked[pool_idx % max(1, len(ranked))] if ranked else a.title
                cleaned.append(_short(filler, 120))
                pool_idx += 1
            return {
                "title": title,
                "bullets": cleaned,
                "notes": _ensure_min_len(notes, 60, a),
                "slide_type": slide_type,
            }

        slides = [
            safe_slide(
                a.title[:80],
                [_short(ranked[0] if ranked else a.title, 110),
                 "Open Notebook artifact generation suite"],
                f"Open the session by framing the topic: {a.title}. "
                "Set expectations for the next few slides.",
                "title",
            ),
            safe_slide(
                "Agenda",
                [f"{kw.title()}" for kw in kws[:5]] or ["Overview", "Deep dive"],
                "Walk through the agenda. Highlight which sections will "
                "carry the most weight and why.",
                "agenda",
            ),
        ]
        for kw in kws[:5]:
            mentions = a.sentences_mentioning(kw)[:3]
            bullets = [_short(s, 110) for s in mentions] or [
                _short(ranked[0] if ranked else a.title, 110),
                f"Core concept: {kw}",
            ]
            slides.append(safe_slide(
                kw.title(),
                bullets,
                "Spend time on the concrete details here. Reference the "
                f"underlying claim about {kw} and how it supports the argument.",
                "content",
            ))
        if numeric_sents:
            slides.append(safe_slide(
                "Key Numbers",
                [_short(s, 120) for s in numeric_sents[:4]],
                "Draw attention to these metrics. They should anchor the "
                "rest of the discussion.",
                "stat",
            ))
        slides.append(safe_slide(
            "Conclusion",
            [_short(ranked[-1] if ranked else a.title, 120),
             "Questions and next steps"],
            "Close with the core takeaway and invite discussion.",
            "closing",
        ))
        plan = {
            "narrative_arc": arc,
            "slide_budget": len(slides),
            "sections": ["Opening", "Context", "Core points", "Evidence", "Closing"],
            "goal": f"Communicate: {a.title}",
            "key_message": ranked[0] if ranked else a.title,
        }
        return {
            "title": a.title[:80],
            "subtitle": _short(ranked[0] if ranked else a.title, 90),
            "plan": plan,
            "slides": slides[:12],
        }

    def _pitch_deck(self, a: _Analysis, hint: str, raw: str) -> Dict[str, Any]:
        ranked = a.rank(14)
        numeric = [s for s in a.sentences if any(n in s for n in a.numbers)]
        problem = next((s for s in a.sentences if "problem" in s.lower()), ranked[0] if ranked else a.title)
        solution = next((s for s in a.sentences if "solution" in s.lower()),
                        next((s for s in a.sentences if "we " in s.lower()), ranked[1] if len(ranked) > 1 else a.title))
        market = next((s for s in a.sentences if "market" in s.lower()), numeric[0] if numeric else ranked[0])
        traction = next((s for s in a.sentences
                         if any(k in s.lower() for k in ["customer", "arr", "revenue", "users"])),
                        numeric[0] if numeric else "Traction details to be expanded.")
        team = next((s for s in a.sentences if "team" in s.lower() or "co-founded" in s.lower()),
                    "Team details to be expanded.")
        ask = next((s for s in a.sentences if "raising" in s.lower() or "ask" in s.lower()),
                   "Raising a strategic round.")
        def s(bullets, title, slide_type="content"):
            cleaned = [_short(b, 120) for b in bullets[:4] if b]
            while len(cleaned) < 2:
                filler = ranked[len(cleaned) % max(1, len(ranked))] if ranked else a.title
                cleaned.append(_short(filler, 120))
            return {
                "title": title,
                "bullets": cleaned[:5],
                "notes": _ensure_min_len(
                    f"On the {title} slide, emphasise the narrative connection "
                    "to the previous slide.",
                    60, a,
                ),
                "slide_type": slide_type,
            }
        slides = [
            s([a.title, ranked[0] if ranked else a.title], a.title[:60], "title"),
            s([problem, "Current alternatives fall short."], "Problem"),
            s([solution, "The approach differs in these specific ways."], "Solution"),
            s([market] + (numeric[:2] if numeric else ["Large total addressable market."]), "Market"),
            s(ranked[2:5] or ["Core product capabilities.", "Key differentiators."], "Product"),
            s([traction, "Measurable momentum across customer segments."], "Traction", "stat"),
            s([team, "Relevant operator experience."], "Team"),
            s([ask, "Use of proceeds across hiring and GTM."], "Ask", "closing"),
        ]
        return {
            "title": a.title[:60],
            "tagline": _ensure_min_len(
                _short(ranked[0] if ranked else a.title, 110), 20, a,
            ),
            "slides": slides,
        }

    def _paper_figure(self, a: _Analysis, hint: str, raw: str) -> Dict[str, Any]:
        nums = re.findall(r"(\d+(?:\.\d+)?)", a.raw)
        kws = a.kw[:4] or ["A", "B", "C"]
        # Greedy: try to find series-like structure "NAME: X Y Z"
        rows = []
        for line in a.raw.splitlines():
            m = re.match(
                r"\s*([A-Z][A-Za-z0-9\-\s]{3,40}?):\s*(.+)", line
            )
            if m:
                numeric_values = re.findall(r"\d+(?:\.\d+)?", m.group(2))
                if len(numeric_values) >= 2:
                    rows.append((m.group(1).strip(), [float(n) for n in numeric_values[:6]]))
        series = []
        if len(rows) >= 2 and len(set(len(v) for _, v in rows)) == 1:
            # Grouped bar chart derived from rows.
            n_cols = len(rows[0][1])
            cats = [kws[i] if i < len(kws) else f"Col {i+1}" for i in range(n_cols)]
            for name, values in rows:
                series.append({
                    "name": name,
                    "data": [{"x": cats[i], "y": v} for i, v in enumerate(values)],
                })
            chart_type = "grouped_bar" if len(series) > 1 else "bar"
        else:
            # Fallback: single bar chart from keyword counts.
            counts = Counter(a.tokens)
            series.append({
                "name": "Frequency",
                "data": [{"x": kw, "y": float(counts[kw])} for kw in kws[:5]],
            })
            chart_type = "bar"
        return {
            "title": f"Figure: {a.title[:80]}",
            "chart_type": chart_type,
            "x_label": "Category",
            "y_label": "Value",
            "series": series[:4],
            "caption": _ensure_min_len(
                f"Figure derived from the source material: {a.title}",
                60, a,
            ),
            "highlight_series": series[-1]["name"] if len(series) >= 2 else None,
        }


# ----------------------------------------------------------------------
# Tiny utilities used by the composers
# ----------------------------------------------------------------------

def _short(text: str, max_len: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= max_len else text[: max_len - 1].rstrip() + "…"


def _ensure_min_len(text: str, min_len: int, a: _Analysis) -> str:
    if not text:
        text = a.title
    while len(text) < min_len:
        extra = next(
            (s for s in a.sentences if s not in text), a.title
        )
        text = f"{text} {extra}"
    return text.strip()


def _topup(existing: List[str], min_n: int, pool: List[str]) -> List[str]:
    out = [x for x in existing if x]
    for candidate in pool:
        if len(out) >= min_n:
            break
        if candidate not in out:
            out.append(candidate)
    while len(out) < min_n:
        out.append("Additional detail pending.")
    return out


def _topup_obj(
    existing: List[Dict[str, Any]], min_n: int, bloom_levels: List[str], kws: List[str]
) -> List[Dict[str, Any]]:
    out = list(existing)
    i = 0
    while len(out) < min_n:
        level = bloom_levels[i % len(bloom_levels)]
        kw = kws[(i + len(out)) % len(kws)] if kws else "the material"
        out.append({
            "bloom_level": level,
            "statement": f"{_objective_verb(level)} {kw}.",
        })
        i += 1
    return out


def _objective_verb(bloom: str) -> str:
    return {
        "remember": "Recall",
        "understand": "Explain",
        "apply": "Apply",
        "analyze": "Analyse",
        "evaluate": "Evaluate",
        "create": "Design",
    }.get(bloom, "Explain")


def _derive_purpose(a: _Analysis, hint: str) -> str:
    low = hint.lower()
    if any(k in low for k in ["briefing", "memo", "announcement"]):
        return "Brief leadership on a current initiative."
    if "research" in low or "paper" in low or "arxiv" in a.raw.lower():
        return "Document a research contribution and its evaluation."
    if "faq" in low:
        return "Answer common questions about the material."
    return "Inform the reader about the material at hand."


def _derive_audience(a: _Analysis, hint: str) -> str:
    low = hint.lower()
    if "executive" in low or "leadership" in low:
        return "Executive leadership"
    if "student" in low or "study" in low:
        return "Self-study learners"
    if "investor" in low or "pitch" in low:
        return "Prospective investors"
    return "Informed practitioners"


def _extract_audience_hint(hint: str) -> str:
    low = hint.lower()
    m = re.search(r"audience is:\s*([^\n\.]+)", low)
    if m:
        return m.group(1).strip().capitalize()
    if "executive" in low:
        return "Executive leadership"
    if "engineer" in low:
        return "Engineering team"
    return "Decision-makers"


def _derive_actions(a: _Analysis) -> List[str]:
    verbs = ["Review", "Validate", "Align on", "Schedule", "Document", "Escalate"]
    actions: List[str] = []
    for i, kw in enumerate(a.kw[:6]):
        verb = verbs[i % len(verbs)]
        actions.append(f"{verb} the plan for {kw}.")
    return actions


def _default_actions(a: _Analysis) -> List[str]:
    return [
        f"Review the highest-importance findings.",
        f"Schedule a follow-up on open questions.",
        f"Document decisions and next steps.",
    ]


def _canonicalize_date(label: str) -> str:
    label = label.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", label):
        return label
    m = re.match(r"([A-Za-z]+)\s+(\d{4})", label)
    if m:
        month_map = {
            "jan": "01", "feb": "02", "mar": "03", "apr": "04",
            "may": "05", "jun": "06", "jul": "07", "aug": "08",
            "sep": "09", "sept": "09", "oct": "10", "nov": "11", "dec": "12",
        }
        mo = month_map.get(m.group(1)[:4].lower())
        if mo:
            return f"{m.group(2)}-{mo}"
    m = re.match(r"([A-Za-z]+)\s+(\d{1,2}),?\s*(\d{4})", label)
    if m:
        month_map = {
            "january": "01", "february": "02", "march": "03", "april": "04",
            "may": "05", "june": "06", "july": "07", "august": "08",
            "september": "09", "october": "10", "november": "11", "december": "12",
        }
        mo = month_map.get(m.group(1).lower()[:9])
        if mo:
            return f"{m.group(3)}-{mo}-{int(m.group(2)):02d}"
    if re.fullmatch(r"\d{4}", label):
        return label
    return label


def _icon_for(keyword: str) -> str:
    kw = keyword.lower()
    if any(k in kw for k in ["time", "year", "date"]):
        return "clock"
    if any(k in kw for k in ["grow", "revenue", "value"]):
        return "chart"
    if any(k in kw for k in ["secur", "risk", "threat"]):
        return "shield"
    if any(k in kw for k in ["user", "member", "team"]):
        return "people"
    return "chart"


def _find_block(raw: str, marker: str) -> str:
    m = re.search(rf"{re.escape(marker)}[^\n]*\n(.+?)(?:\n\n|$)", raw, re.DOTALL)
    return (m.group(1) if m else "").strip()


def _find_json_block(raw: str, marker: str) -> Optional[Dict[str, Any]]:
    m = re.search(rf"{re.escape(marker)}[^\n]*\n(\{{.+?\}})\s*\n", raw, re.DOTALL)
    if not m:
        return None
    try:
        import json
        return json.loads(m.group(1))
    except Exception:
        return None


def _collect_bullets(draft_json: Dict[str, Any]) -> List[str]:
    """Flatten bullet-like strings from a structured draft."""
    out: List[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, str):
            if 4 <= len(node.split()) < 40:
                out.append(node)
        elif isinstance(node, list):
            for x in node:
                walk(x)
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)
    walk(draft_json)
    return out
