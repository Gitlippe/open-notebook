"""Demo: Mind map of distributed systems fundamentals."""
from __future__ import annotations

import asyncio

from demos._common import run_demo


SOURCE = {
    "title": "Distributed Systems Overview",
    "content": """
Distributed systems are collections of independent computers that appear
to users as a single coherent system. Core concerns include consistency,
availability, and partition tolerance (the CAP theorem), communication
protocols, consensus, fault tolerance, and scalability.

Consistency models span a spectrum. Strong consistency (linearisability)
requires every read to see the latest write. Eventual consistency permits
temporary divergence as long as all replicas converge in absence of
further writes. Causal consistency preserves cause-effect ordering.

Consensus algorithms let a set of nodes agree on a value despite failures.
Paxos was the seminal algorithm; Raft is a more understandable
reformulation. Byzantine fault-tolerant variants (PBFT, HotStuff) tolerate
arbitrary node misbehaviour, including malice.

Communication happens over unreliable networks. Systems use RPC, message
queues, publish-subscribe, or streaming frameworks. Idempotence, retries,
and timeouts are essential for correctness.

Storage layers include replicated logs, distributed key-value stores
(DynamoDB, Cassandra), distributed file systems (HDFS, Ceph), and
analytical stores (BigQuery, Snowflake).

Observability — metrics, logs, traces — is not optional; at scale, debugging
is impossible without distributed tracing and structured logging.
"""
}


async def main():
    await run_demo(
        name="mindmap",
        artifact_type="mindmap",
        sources=[SOURCE],
        title="Distributed Systems",
    )


if __name__ == "__main__":
    asyncio.run(main())
