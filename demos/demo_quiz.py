"""Demo: Multiple-choice quiz from a biology chapter."""
from __future__ import annotations

import asyncio

from demos._common import run_demo


SOURCE = {
    "title": "Cell Biology Chapter: Mitochondria",
    "content": """
Mitochondria are double-membrane organelles found in most eukaryotic
cells. They are commonly described as the powerhouses of the cell because
they generate most of the cell's supply of adenosine triphosphate (ATP),
used as a source of chemical energy.

Mitochondria contain their own DNA, which is circular and inherited
exclusively from the mother. This unusual property is exploited by
researchers to trace maternal lineage in population genetics. The DNA
encodes a small number of proteins involved in the electron transport
chain, while the majority of mitochondrial proteins are encoded in the
nuclear genome and imported into the organelle.

The inner mitochondrial membrane is highly folded into structures called
cristae, which increase surface area for the proton-pumping complexes of
the electron transport chain. The space between the inner and outer
membranes is called the intermembrane space; the interior enclosed by the
inner membrane is called the matrix.

ATP synthesis occurs via oxidative phosphorylation, in which electrons
derived from glucose breakdown are passed along the electron transport
chain. This pumps protons from the matrix into the intermembrane space.
The resulting proton gradient drives ATP synthase, which phosphorylates
ADP to produce ATP.

Apoptosis, or programmed cell death, is triggered in part by the release
of cytochrome c from mitochondria into the cytosol, where it activates
caspase enzymes.
"""
}


async def main():
    await run_demo(
        name="quiz",
        artifact_type="quiz",
        sources=[SOURCE],
        title="Mitochondria Quiz",
        config={"question_count": 6},
    )


if __name__ == "__main__":
    asyncio.run(main())
