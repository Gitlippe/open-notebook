"""Demo: Publication-style figure comparing benchmarks.

When run with ``ARTIFACT_USE_LLM=1`` the LLM is asked to decide the chart
type and provide the data. Offline, we supply structured numeric data
directly through an injected LLM fixture so the figure reflects real
numbers rather than heuristic placeholders.
"""
from __future__ import annotations

import asyncio

from demos._common import offline_mode, run_demo
from open_notebook.artifacts.llm import ArtifactLLM, make_echo_generator


SOURCE = {
    "title": "LLM Agent Benchmark — Distyl 2026 Q2 Internal Report",
    "content": """
We benchmarked four agent architectures on WebArena, AIME 2024, and
HumanEval. Scores are the mean pass@1 across three runs with different
random seeds. Higher is better.

Baseline (GPT-4o, no tools): WebArena 21.4, AIME 31.0, HumanEval 78.2.

ReAct agent: WebArena 34.8, AIME 38.7, HumanEval 81.0.

Voyager-style skills library: WebArena 42.1, AIME 44.2, HumanEval 82.5.

Training-Free GRPO (experience library): WebArena 47.3, AIME 49.8,
HumanEval 84.4.
"""
}


def _benchmark_data(_prompt: str):
    """Canonical structured figure data for the demo."""
    return {
        "title": "LLM agent architectures across benchmarks",
        "chart_type": "bar",
        "x_label": "Benchmark",
        "y_label": "Pass@1 (%)",
        "series": [
            {
                "name": "Baseline",
                "data": [
                    {"x": "WebArena", "y": 21.4},
                    {"x": "AIME 2024", "y": 31.0},
                    {"x": "HumanEval", "y": 78.2},
                ],
            },
            {
                "name": "ReAct",
                "data": [
                    {"x": "WebArena", "y": 34.8},
                    {"x": "AIME 2024", "y": 38.7},
                    {"x": "HumanEval", "y": 81.0},
                ],
            },
            {
                "name": "Voyager skills",
                "data": [
                    {"x": "WebArena", "y": 42.1},
                    {"x": "AIME 2024", "y": 44.2},
                    {"x": "HumanEval", "y": 82.5},
                ],
            },
            {
                "name": "Training-Free GRPO",
                "data": [
                    {"x": "WebArena", "y": 47.3},
                    {"x": "AIME 2024", "y": 49.8},
                    {"x": "HumanEval", "y": 84.4},
                ],
            },
        ],
        "caption": (
            "Pass@1 (%) on WebArena, AIME 2024, and HumanEval across four "
            "LLM agent architectures; Training-Free GRPO achieves the best "
            "average score with no parameter updates."
        ),
    }


async def main():
    if offline_mode():
        from demos._common import banner, demo_output_dir, print_result
        from open_notebook.artifacts import generate_artifact

        banner("paper_figure", "paper_figure")
        print("(Offline mode: using injected canned structured data.)")
        llm = ArtifactLLM(text_generator=make_echo_generator(_benchmark_data))
        result = await generate_artifact(
            artifact_type="paper_figure",
            sources=[SOURCE],
            title="LLM Agent Benchmark",
            output_dir=demo_output_dir("paper_figure"),
            llm=llm,
        )
        print_result(result)
    else:
        await run_demo(
            name="paper_figure",
            artifact_type="paper_figure",
            sources=[SOURCE],
            title="LLM Agent Benchmark",
            config={"chart_type": "bar"},
        )


if __name__ == "__main__":
    asyncio.run(main())
