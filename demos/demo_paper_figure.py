"""Demo: Publication-style figure comparing benchmark results.

The source contains rows of labelled benchmark numbers. The real-LLM
pipeline asks the model to design the figure; the offline backend
(StructuredMockChat) parses the rows directly from the source text and
picks the right chart_type (grouped_bar for multi-series tabular data).
Either way, the figure renders real numbers from the source.
"""
from __future__ import annotations

import asyncio

from demos._common import run_demo


SOURCE = {
    "title": "LLM Agent Benchmark — Distyl 2026 Q2 Internal Report",
    "content": """
We benchmarked four agent architectures on WebArena, AIME 2024, and
HumanEval. Scores are the mean pass@1 across three runs with different
random seeds. Higher is better.

Baseline: WebArena 21.4, AIME 31.0, HumanEval 78.2.
ReAct agent: WebArena 34.8, AIME 38.7, HumanEval 81.0.
Voyager skills: WebArena 42.1, AIME 44.2, HumanEval 82.5.
Training-Free GRPO: WebArena 47.3, AIME 49.8, HumanEval 84.4.

Training-Free GRPO achieves the best average score with no parameter
updates, supporting the hypothesis that experience-library prompting
generalises across benchmarks.
"""
}


async def main():
    await run_demo(
        name="paper_figure",
        artifact_type="paper_figure",
        sources=[SOURCE],
        title="LLM Agent Benchmark",
        config={"chart_type": "grouped_bar"},
    )


if __name__ == "__main__":
    asyncio.run(main())
