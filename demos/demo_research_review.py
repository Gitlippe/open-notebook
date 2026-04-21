"""Demo: Research review (BLUF) of the Training-Free GRPO paper.

This mirrors the style of internal skeptical research reviews — a BLUF,
notable authors, short take, why-we-care with direct techniques and cost
analysis, methodological limitations, and potential applications.
"""
from __future__ import annotations

import asyncio

from demos._common import run_demo


SOURCE = {
    "title": "Training-Free Group Relative Policy Optimization",
    "author": "Yuzheng Cai, Siqi Cai, Yuchen Shi, Zihan Xu (equal contribution) | Ke Li (correspondence)",
    "published_at": "2025-10-09",
    "url": "https://arxiv.org/abs/2510.08191",
    "content": """
Affiliations: Tencent Youtu Lab, Fudan University, Xiamen University.

The paper proposes "Training-Free GRPO" — doing GRPO-style RL optimization
through prompt engineering (no parameter updates). The method has four
steps: (1) generate multiple rollouts per query, (2) use the LLM to
introspect on successes/failures and extract natural language
"experiences," (3) iteratively refine this experience library over epochs,
(4) inject experiences as context during inference.

On AIME 2024/2025 math benchmarks, they improve DeepSeek-V3.1-Terminus
(671B parameters) from 80.0% to 82.7% with just 100 training samples.
They claim 100x less data and 500x lower cost than fine-tuning 32B models
(roughly $18 versus $10,000).

The authors never compare their method to traditional GRPO on the same
base model. They compare a 671B frozen model to fine-tuned 32B models,
which makes it impossible to attribute the gain to their method versus
just using a larger model. This is a significant methodological flaw.

Domains tested: math reasoning (AIME 2024/2025) and web search
(WebWalkerQA). The authors acknowledge the method may not generalise to
domains with subjective or ambiguous quality. Despite the "training-free"
name, the experience learning phase still requires ground-truth labels;
the w/o ground truths ablation shows clear degradation.

Resources: arXiv preprint (not peer-reviewed),
https://github.com/TencentCloudADP/youtu-agent/tree/training_free_GRPO

Potential applications include rapid domain adaptation for deployed
frozen large models, building task-specific prompt libraries through
systematic trajectory comparison, and low-cost experimentation before
committing to expensive fine-tuning runs.
"""
}


async def main():
    await run_demo(
        name="research_review",
        artifact_type="research_review",
        sources=[SOURCE],
        title="Research Review: Training-Free GRPO",
        config={"tone": "brutally honest, skeptical"},
    )


if __name__ == "__main__":
    asyncio.run(main())
