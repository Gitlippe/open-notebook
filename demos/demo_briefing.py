"""Demo: Executive briefing (BLUF) from a product-launch memo."""
from __future__ import annotations

import asyncio

from demos._common import run_demo


SOURCE = {
    "title": "Q3 Launch Internal Memo",
    "author": "VP of Product",
    "published_at": "2026-04-18",
    "content": """
We are shipping the Compass release of our analytics platform next Wednesday.
Compass targets mid-market customers who have outgrown spreadsheets but find
existing BI tools too complex. The key differentiator is the natural-language
query interface backed by a learned schema graph: customers ask questions in
plain English and receive charts and narrative answers within five seconds.

In pilot testing, the average time-to-first-insight dropped from 42 minutes
to 3 minutes. Net promoter score from pilot customers is 62, up from 34
with our prior product. Conversion from free trial to paid plan was 41%,
double the industry benchmark.

The release carries operational risk. We are introducing a new vector
database and our SRE team has flagged that we do not yet have a tested
rollback procedure for the embedding service. Customer support has also
raised concerns that pricing changes (a 15% increase for the analytics
tier) were announced only 14 days before launch. Leadership has agreed
to honour legacy pricing for the next two billing cycles.

Expected revenue impact for Q4 is $4.8M incremental ARR if current pilot
conversion rates hold. Investor communications will go out the morning
of launch; a customer webinar is scheduled for the following day.
"""
}


async def main():
    await run_demo(
        name="briefing",
        artifact_type="briefing",
        sources=[SOURCE],
        title="Compass Launch Briefing",
        config={"audience": "Executive leadership team"},
    )


if __name__ == "__main__":
    asyncio.run(main())
