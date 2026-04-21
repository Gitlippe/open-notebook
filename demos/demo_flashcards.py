"""Demo: Anki flashcards from a machine-learning glossary."""
from __future__ import annotations

import asyncio

from demos._common import run_demo


SOURCE = {
    "title": "Machine Learning Glossary",
    "content": """
Gradient descent is an optimization algorithm that iteratively adjusts
parameters in the direction of the negative gradient of the loss.

Overfitting occurs when a model performs well on training data but fails
to generalise to unseen data. Regularisation, early stopping, and data
augmentation are common mitigations.

Cross-validation is a procedure for estimating model skill by partitioning
data into folds and rotating which fold acts as the test set.

The bias-variance trade-off describes the tension between underfitting
(high bias) and overfitting (high variance); the goal is to minimise
total error, not any individual component.

Backpropagation is the algorithm used to compute gradients in neural
networks by applying the chain rule from output to input.

Embedding is a learned mapping from discrete symbols (words, items) to
continuous vectors that preserve meaningful similarity.

Transfer learning is the practice of reusing a model trained on one task
as the starting point for training on a different, often related task.

Fine-tuning is the process of continuing training on a specific task
with a smaller learning rate, using a pretrained model as initialisation.
"""
}


async def main():
    await run_demo(
        name="flashcards",
        artifact_type="flashcards",
        sources=[SOURCE],
        title="ML Glossary Flashcards",
        config={"card_count": 12},
    )


if __name__ == "__main__":
    asyncio.run(main())
