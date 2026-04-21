"""Demo: Informational slide deck summarising a technical topic."""
from __future__ import annotations

import asyncio

from demos._common import run_demo


SOURCE = {
    "title": "Retrieval-Augmented Generation — Field Guide",
    "content": """
Retrieval-Augmented Generation (RAG) pairs a language model with an
external knowledge store. The model is asked a question, relevant
documents are retrieved, and the model generates an answer grounded in
the retrieved content.

RAG is the standard approach when you need up-to-date or private
information that was not present during model training. It is cheaper
than fine-tuning, easier to update (swap the index, not the weights),
and produces citable answers.

A minimal RAG pipeline has four components: (1) an embedder that turns
text into vectors, (2) a vector store that retrieves nearest-neighbour
documents, (3) a prompt template that injects retrieved context into the
LLM's input, (4) the LLM itself which produces the final answer.

Quality depends heavily on retrieval. Chunking strategy (fixed-size,
sentence-aware, or semantic) affects recall. Reranking models (cross-
encoders) applied to top-k candidates significantly improve precision.
Hybrid retrieval combining BM25 with dense vectors outperforms either
alone on most benchmarks.

Common failure modes include retrieval of plausibly similar but
irrelevant passages ("lost in the middle" problem), over-reliance on
retrieved content even when the query is knowledge-free, and context
window exhaustion on long documents. Mitigations include self-RAG,
graph-based retrieval, and explicit query rewriting.

For production deployments, latency budgets typically allocate ~300 ms
to retrieval and ~1-3 s to generation. P99 latency is dominated by the
slowest chunk in the retrieval stack.
"""
}


async def main():
    await run_demo(
        name="slide_deck",
        artifact_type="slide_deck",
        sources=[SOURCE],
        title="RAG Field Guide",
        config={"length": "standard"},
    )


if __name__ == "__main__":
    asyncio.run(main())
