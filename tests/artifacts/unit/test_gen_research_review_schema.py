"""Unit tests for ResearchReviewGenerator — schema, registry, and config contract.

No real LLM calls. All assertions are structural / contract-level.
"""
from __future__ import annotations

import pytest

from open_notebook.artifacts.generators.research_review import (
    ResearchReviewGenerator,
    ResearchReviewSchema,
    WhyWeCareSchema,
    ResourceSchema,
)
from open_notebook.artifacts.registry import ARTIFACT_TYPES


pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# 1. Schema has required fields
# ---------------------------------------------------------------------------

class TestResearchReviewSchema:
    def test_schema_has_bluf(self):
        assert "bluf" in ResearchReviewSchema.model_fields

    def test_schema_has_title(self):
        assert "title" in ResearchReviewSchema.model_fields

    def test_schema_has_limitations(self):
        assert "limitations" in ResearchReviewSchema.model_fields

    def test_schema_has_potential_applications(self):
        assert "potential_applications" in ResearchReviewSchema.model_fields

    def test_schema_has_why_we_care(self):
        assert "why_we_care" in ResearchReviewSchema.model_fields

    def test_why_we_care_schema_fields(self):
        fields = WhyWeCareSchema.model_fields
        assert "direct_techniques" in fields
        assert "cost_effectiveness" in fields
        assert "limitations" in fields

    def test_resource_schema_fields(self):
        assert "label" in ResourceSchema.model_fields
        assert "url" in ResourceSchema.model_fields

    def test_schema_validates_complete_review(self):
        review = ResearchReviewSchema(
            title="Research Review: Training-Free GRPO",
            bluf="Interesting but unvalidated against traditional GRPO baseline.",
            notable_authors=["Cai", "Siqi"],
            affiliations=["Tencent"],
            short_take="A 3-sentence summary.",
            why_we_care=WhyWeCareSchema(
                direct_techniques=["Prompt-based rollouts"],
                cost_effectiveness=["100x cheaper than fine-tuning"],
                limitations=["No baseline comparison"],
            ),
            limitations=["No comparison to traditional GRPO"],
            potential_applications=["Internal RLHF experiments"],
            resources=[ResourceSchema(label="arXiv", url="https://arxiv.org/")],
        )
        assert review.bluf.startswith("Interesting")
        assert len(review.limitations) == 1
        assert len(review.resources) == 1

    def test_schema_round_trips(self):
        review = ResearchReviewSchema(
            title="Review: Foo",
            bluf="Verdict.",
            short_take="Summary.",
            limitations=["Limit A"],
            potential_applications=["Use A"],
        )
        restored = ResearchReviewSchema.model_validate(review.model_dump())
        assert restored.bluf == "Verdict."
        assert restored.limitations == ["Limit A"]


# ---------------------------------------------------------------------------
# 2. Generator class is in ARTIFACT_TYPES
# ---------------------------------------------------------------------------

class TestResearchReviewGeneratorRegistry:
    def test_generator_registered(self):
        assert "research_review" in ARTIFACT_TYPES

    def test_registered_class_is_research_review_generator(self):
        assert ARTIFACT_TYPES["research_review"] is ResearchReviewGenerator


# ---------------------------------------------------------------------------
# 3. Generator's default_model_type is set
# ---------------------------------------------------------------------------

class TestResearchReviewGeneratorConfig:
    def test_default_model_type_is_set(self):
        assert ResearchReviewGenerator.default_model_type
        assert isinstance(ResearchReviewGenerator.default_model_type, str)

    def test_artifact_type_is_research_review(self):
        assert ResearchReviewGenerator.artifact_type == "research_review"

    def test_description_mentions_bluf(self):
        assert "BLUF" in ResearchReviewGenerator.description or "bluf" in ResearchReviewGenerator.description.lower()
