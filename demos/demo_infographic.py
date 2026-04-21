"""Demo: Infographic summarising open-source repository metrics."""
from __future__ import annotations

import asyncio

from demos._common import run_demo


SOURCE = {
    "title": "Open Notebook — Annual Community Report 2025",
    "content": """
Open Notebook is an open-source alternative to Google's NotebookLM. Over
the past year the project has grown from 2,100 to 5,400 GitHub stars, a
157% increase. The maintainer team expanded from 1 to 4 core
contributors; the long-tail of one-time contributors is now 92 people
across 27 countries.

The codebase reached 48,000 lines of Python plus 22,000 lines of
TypeScript. 82% of the code is covered by automated tests. The Docker
image has been pulled 145,000 times.

The community Discord grew to 1,800 members. The project merged 312 pull
requests and closed 480 issues. Median time-to-first-response on new
issues is 18 hours.

Key milestones: multi-provider AI support (8+ providers), podcast
generation via podcast-creator, multimodal content ingestion,
SurrealDB-backed semantic search, and the 2.0 UI built on Next.js 16.
"""
}


async def main():
    await run_demo(
        name="infographic",
        artifact_type="infographic",
        sources=[SOURCE],
        title="Open Notebook Year in Review",
        config={"color_theme": "green"},
    )


if __name__ == "__main__":
    asyncio.run(main())
