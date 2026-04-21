"""Demo: Timeline of the history of large language models."""
from __future__ import annotations

import asyncio

from demos._common import run_demo


SOURCE = {
    "title": "A Brief History of Large Language Models",
    "content": """
In 2017 Vaswani et al. published "Attention Is All You Need," introducing
the Transformer architecture that underpins every modern language model.

In 2018 OpenAI released GPT-1, demonstrating that generative pretraining
followed by task-specific fine-tuning could reach state-of-the-art on
natural language understanding benchmarks. The same year Google released
BERT, which quickly became a dominant encoder model for NLP.

In 2019 OpenAI released GPT-2 with 1.5B parameters. Concerns about
misuse delayed the full release by several months.

In 2020 GPT-3 (175B parameters) demonstrated strong few-shot learning,
sparking the modern era of prompt engineering.

In 2022 OpenAI launched ChatGPT in November, catalysing mainstream
adoption of conversational AI. The same year saw the release of
InstructGPT, which introduced reinforcement learning from human feedback
(RLHF) as a training-time technique.

In 2023 Meta open-sourced LLaMA and LLaMA 2, seeding a vibrant open
ecosystem. Anthropic released Claude, and Google released Gemini.

In 2024 reasoning models like OpenAI o1 and DeepSeek-R1 showed that
long chain-of-thought training could improve mathematical and code
performance dramatically.

In 2025 the field saw a wave of training-free and agent-based approaches,
including Training-Free GRPO (October 2025) which applied RL-style
optimization via prompt engineering alone.
"""
}


async def main():
    await run_demo(
        name="timeline",
        artifact_type="timeline",
        sources=[SOURCE],
        title="History of LLMs",
    )


if __name__ == "__main__":
    asyncio.run(main())
