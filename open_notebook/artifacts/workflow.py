"""Multi-step workflow primitives for artifact generation.

The key pattern every SOTA generator follows:

    claims  = extract_claims(sources)            # Phase 1
    draft   = llm.structured(DraftSchema, ...)   # Phase 2
    critique = llm.structured(Critique, ...)     # Phase 3
    draft   = llm.structured(DraftSchema, ...,   # Phase 4
                             refine_with=critique)

This module factors the claim-extraction and critique-refine loop so every
generator can compose them without reinventing.
"""
from __future__ import annotations

from typing import List, Optional, Type, TypeVar

from loguru import logger
from pydantic import BaseModel

from open_notebook.artifacts.llm import ArtifactLLM
from open_notebook.artifacts.schemas import ClaimSet, Critique

T = TypeVar("T", bound=BaseModel)


# ----------------------------------------------------------------------
# Phase 1: claim extraction
# ----------------------------------------------------------------------

CLAIM_EXTRACTION_SYSTEM = (
    "You are a meticulous analyst. Your job is to read source material and "
    "extract the atomic claims, named entities, and numeric facts it contains. "
    "Do not add commentary. Do not invent facts — every claim must be backed "
    "by a direct evidence pointer from the source. Prefer short, precise "
    "claims over long ones."
)


async def extract_claims(
    llm: ArtifactLLM,
    sources_text: str,
    *,
    focus: Optional[str] = None,
) -> ClaimSet:
    directive = CLAIM_EXTRACTION_SYSTEM
    if focus:
        directive += f"\n\nFocus the extraction for this purpose: {focus}."
    return await llm.structured(
        system_prompt=directive,
        user_prompt=sources_text,
        schema=ClaimSet,
        temperature=0.0,
    )


def claims_to_context(claim_set: ClaimSet, max_claims: int = 20) -> str:
    """Render a claim set as compact context for downstream prompts."""
    lines = [
        f"TOPIC: {claim_set.topic}",
        f"PURPOSE: {claim_set.purpose}",
        f"ORIGINAL AUDIENCE: {claim_set.audience_hint}",
        "",
        "EXTRACTED CLAIMS:",
    ]
    for idx, claim in enumerate(claim_set.claims[:max_claims], start=1):
        lines.append(
            f"  {idx}. [{claim.importance}/{claim.category}] {claim.text}"
        )
        lines.append(f"     evidence: {claim.evidence}")
    if claim_set.numeric_facts:
        lines.append("")
        lines.append("NUMERIC FACTS:")
        for f in claim_set.numeric_facts:
            lines.append(f"  - {f}")
    if claim_set.named_entities:
        lines.append("")
        lines.append("NAMED ENTITIES: " + ", ".join(claim_set.named_entities[:30]))
    return "\n".join(lines)


# ----------------------------------------------------------------------
# Phases 2 + 3 + 4: draft, critique, refine
# ----------------------------------------------------------------------

async def draft_and_refine(
    llm: ArtifactLLM,
    *,
    schema: Type[T],
    draft_system: str,
    context: str,
    critique_system: Optional[str] = None,
    refinement_system: Optional[str] = None,
    quality_floor: int = 7,
    max_passes: int = 2,
) -> T:
    """Generate an artifact, self-critique, and refine up to ``max_passes``.

    - ``draft_system`` is the artifact-specific prompt.
    - ``context`` is the marshalled claim set / source material.
    - ``critique_system`` defaults to a strict internal reviewer persona.
    - ``refinement_system`` defaults to an 'apply critique' instruction.
    """
    critique_system = critique_system or _DEFAULT_CRITIQUE_SYSTEM
    refinement_system = refinement_system or _DEFAULT_REFINE_SYSTEM

    draft = await llm.structured(
        system_prompt=draft_system,
        user_prompt=context,
        schema=schema,
        temperature=0.2,
    )
    passes = 0
    while passes < max_passes:
        passes += 1
        critique = await llm.structured(
            system_prompt=critique_system.format(
                schema_name=schema.__name__,
            ),
            user_prompt=_format_for_critique(context, draft),
            schema=Critique,
            temperature=0.0,
        )
        logger.debug(
            f"draft_and_refine pass={passes} "
            f"score={critique.quality_score} issues={len(critique.issues)}"
        )
        if critique.quality_score >= quality_floor and not critique.issues:
            return draft
        draft = await llm.structured(
            system_prompt=refinement_system,
            user_prompt=_format_for_refinement(context, draft, critique),
            schema=schema,
            temperature=0.15,
        )
    return draft


_DEFAULT_CRITIQUE_SYSTEM = (
    "You are a senior editor reviewing a draft {schema_name}. Your job is to "
    "tear it apart constructively: identify vague language, unsupported "
    "claims, missing facts, redundant bullets, weak verbs, filler, and any "
    "departure from the source material. Score the draft strictly. Only "
    "praise when genuinely warranted. Output must conform to the Critique "
    "schema."
)

_DEFAULT_REFINE_SYSTEM = (
    "You are rewriting a draft artifact. Apply the reviewer's critique "
    "faithfully: add missing facts from the source context, remove "
    "redundancies, sharpen vague language, and execute each suggested edit. "
    "Preserve all accurate content. Produce the revised artifact in the "
    "same structured schema."
)


def _format_for_critique(context: str, draft: BaseModel) -> str:
    return (
        "SOURCE CONTEXT (ground truth):\n"
        f"{context}\n\n"
        "DRAFT ARTIFACT (JSON):\n"
        f"{draft.model_dump_json(indent=2)}\n\n"
        "Review the draft against the source context and produce a Critique."
    )


def _format_for_refinement(
    context: str, draft: BaseModel, critique: Critique
) -> str:
    return (
        "SOURCE CONTEXT:\n"
        f"{context}\n\n"
        "CURRENT DRAFT:\n"
        f"{draft.model_dump_json(indent=2)}\n\n"
        "REVIEWER CRITIQUE:\n"
        f"{critique.model_dump_json(indent=2)}\n\n"
        "Rewrite the draft applying every issue, missing item, and suggested "
        "edit. Output the refined artifact in the same schema."
    )
