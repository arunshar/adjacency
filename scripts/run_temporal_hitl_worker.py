#!/usr/bin/env python3
"""Run the opt-in Temporal worker for HITL reviews only."""

from __future__ import annotations

import asyncio

from temporalio.worker import Worker

from adjacency.temporal_hitl import HITLReviewWorkflow, TemporalHITLQueue


async def main() -> None:
    queue = await TemporalHITLQueue.connect()
    worker = Worker(
        queue.client,
        task_queue=queue.task_queue,
        workflows=[HITLReviewWorkflow],
    )
    print(f"Temporal HITL worker polling task queue {queue.task_queue}")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
