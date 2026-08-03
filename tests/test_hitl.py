from __future__ import annotations

import asyncio

import pytest

from adjacency.hitl import (
    Adjudication,
    HITLQueueError,
    HumanAction,
    InProcessHITLQueue,
    ReviewRequest,
    ReviewStatus,
    create_hitl_queue,
)


def request(request_id: str = "review-1") -> ReviewRequest:
    return ReviewRequest(
        request_id=request_id,
        trace_id="trace:item-1",
        item_id="item-1",
        policy_hash="policy-hash",
        corpus_hash="corpus-hash",
        reason_codes=("G1_SPAN_NOT_FOUND",),
        source_url="https://x.com/example/status/1",
    )


def test_in_process_queue_is_the_default_even_with_temporal_credentials():
    async def scenario() -> None:
        queue = await create_hitl_queue(
            environ={
                "TEMPORAL_ADDRESS": "unreachable.invalid:7233",
                "TEMPORAL_NAMESPACE": "unused",
                "TEMPORAL_API_KEY": "unused",
            }
        )
        assert isinstance(queue, InProcessHITLQueue)
        pending = await queue.enqueue(request())
        completed = await queue.adjudicate(
            "review-1",
            Adjudication(
                request_id="review-1",
                action=HumanAction.ALLOW,
                adjudicator="human-1",
            ),
        )

        assert pending.status is ReviewStatus.PENDING
        assert completed.status is ReviewStatus.ADJUDICATED
        assert await queue.state("review-1") == completed

    asyncio.run(scenario())


def test_in_process_queue_rejects_invalid_or_unknown_requests():
    async def scenario() -> None:
        queue = InProcessHITLQueue()
        await queue.enqueue(request())

        with pytest.raises(HITLQueueError, match="does not match"):
            await queue.adjudicate(
                "review-1",
                Adjudication(
                    request_id="other-review",
                    action=HumanAction.BLOCK,
                    adjudicator="human-1",
                ),
            )
        with pytest.raises(HITLQueueError, match="unknown review"):
            await queue.state("missing")
        with pytest.raises(HITLQueueError, match="unsupported"):
            await create_hitl_queue("unknown")

    asyncio.run(scenario())
