"""Demo: Study guide from an ML tutorial."""
from __future__ import annotations

import asyncio

from demos._common import run_demo


SOURCE = {
    "title": "A Gentle Introduction to Transformers",
    "content": """
Transformers are a neural network architecture introduced in the 2017 paper
"Attention Is All You Need" by Vaswani et al. Unlike prior sequence models
that processed tokens one at a time (RNNs, LSTMs), transformers operate on
the entire sequence simultaneously using a mechanism called self-attention.

Self-attention computes, for every pair of positions in the input, a score
that quantifies how much one position should influence another. These
scores are normalised via softmax to form attention weights, which are
then used to mix the value vectors. The queries, keys, and values are
linear projections of the input embeddings, making the entire block
differentiable end-to-end.

Multi-head attention runs several attention computations in parallel with
independent parameter sets, then concatenates the outputs. This lets the
model attend to different relationships — syntactic, semantic, positional
— in separate subspaces.

Transformers stack these attention blocks together with feed-forward
networks and residual connections. Positional encodings (sinusoidal or
learned) inject order information because attention is inherently
permutation-invariant.

Today transformers dominate natural language processing (BERT, GPT),
computer vision (Vision Transformer), and multimodal applications
(CLIP, DALL-E, Flamingo). They remain computationally expensive for
long sequences, motivating ongoing research into efficient attention
variants such as linear attention, sparse attention, and state-space
alternatives like Mamba.
"""
}


async def main():
    await run_demo(
        name="study_guide",
        artifact_type="study_guide",
        sources=[SOURCE],
        title="Transformers Study Guide",
        config={"depth": "graduate"},
    )


if __name__ == "__main__":
    asyncio.run(main())
