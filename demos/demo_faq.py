"""Demo: FAQ from a SaaS product announcement."""
from __future__ import annotations

import asyncio

from demos._common import run_demo


SOURCE = {
    "title": "Announcing Linden 2.0",
    "content": """
Today we are releasing Linden 2.0, a full rewrite of our collaborative
document editor. Linden 2.0 replaces the old CRDT engine with Yjs, adds
end-to-end encryption for workspaces on the Team and Enterprise plans,
and introduces a brand-new offline mode that keeps working even when the
device has been offline for up to 30 days.

Pricing is unchanged for existing customers. New customers on the Free
plan now get 10 private documents (up from 3). The Team plan remains $12
per user per month. Enterprise pricing is available on request.

Existing Linden 1.x workspaces will be migrated automatically over the
next two weeks. No user action is required. Legacy API tokens continue
to work until December 31, 2026, at which point v1 of the API will be
retired. We will publish a migration guide for the v2 API in May.

Linden 2.0 is available on web, macOS, Windows, iOS, and Android. Linux
support is in public beta. Self-hosted Enterprise customers can request
the 2.0 container image from their account manager.
"""
}


async def main():
    await run_demo(
        name="faq",
        artifact_type="faq",
        sources=[SOURCE],
        title="Linden 2.0 FAQ",
    )


if __name__ == "__main__":
    asyncio.run(main())
