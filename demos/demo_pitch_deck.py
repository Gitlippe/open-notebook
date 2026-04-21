"""Demo: Venture-style pitch deck for a hypothetical startup."""
from __future__ import annotations

import asyncio

from demos._common import run_demo


SOURCE = {
    "title": "Ravenscroft — Company Overview",
    "content": """
Ravenscroft is an AI-native cybersecurity company focused on detecting
and neutralising LLM-powered phishing and social-engineering attacks
against enterprise customers.

Problem. Large language models have made phishing cheap, contextual, and
linguistically perfect. Traditional email security (DMARC, static pattern
matching, legacy ML classifiers) has not caught up. In the first quarter
of 2026 the volume of AI-generated phishing grew 412% year over year.
Enterprise security teams report a 3-5x increase in successful social-
engineering incidents.

Solution. Ravenscroft analyses inbound messages across email, chat, and
voicemail in real time using a purpose-built LLM fine-tuned on adversarial
examples. The system scores messages on a combined axis of linguistic
authenticity, contextual coherence, and behavioural fingerprint of the
purported sender. Detections feed into existing SIEMs via a Splunk and
CrowdStrike integration.

Market. The email security market alone is $5.2B and growing 12% CAGR.
The adjacent insider-threat and identity-protection markets add another
$8.1B. Our beachhead is Fortune 500 enterprises with >10,000 employees.

Product. Ravenscroft is a SaaS platform with a browser extension for
real-time warnings, an admin dashboard for incident investigation, and a
programmatic API for custom integrations. We are SOC 2 Type II compliant.

Traction. 17 paying customers, $2.4M ARR, 140% net revenue retention. Top
3 customers by logo are in financial services.

Team. Co-founded by a former NSA red-team lead and the first staff
security engineer at Stripe. Engineering team of 14.

Ask. Raising a $22M Series A to expand the enterprise go-to-market motion
and build out the detection research team.
"""
}


async def main():
    await run_demo(
        name="pitch_deck",
        artifact_type="pitch_deck",
        sources=[SOURCE],
        title="Ravenscroft — Series A Pitch",
        config={"company": "Ravenscroft"},
    )


if __name__ == "__main__":
    asyncio.run(main())
