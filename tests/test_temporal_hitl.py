from __future__ import annotations

import asyncio

import pytest

from adjacency.hitl import (
    Adjudication,
    HumanAction,
    ReviewRequest,
    ReviewStatus,
)

pytest.importorskip("temporalio")

pytestmark = pytest.mark.integration


def request() -> ReviewRequest:
    return ReviewRequest(
        request_id="temporal-review-1",
        trace_id="trace:item-1",
        item_id="item-1",
        policy_hash="policy-hash",
        corpus_hash="corpus-hash",
        reason_codes=("G1_SPAN_NOT_FOUND",),
        source_url="https://x.com/example/status/1",
    )


def test_workflow_exposes_one_state_query_and_applies_one_adjudication_signal():
    from adjacency.temporal_hitl import HITLReviewWorkflow

    workflow_instance = HITLReviewWorkflow(request())
    pending = workflow_instance.queue_state()
    workflow_instance.adjudicate(
        Adjudication(
            request_id=request().request_id,
            action=HumanAction.BLOCK,
            adjudicator="human-1",
        )
    )
    completed = workflow_instance.queue_state()

    assert pending.status is ReviewStatus.PENDING
    assert completed.status is ReviewStatus.ADJUDICATED
    assert completed.adjudication is not None
    assert completed.adjudication.action is HumanAction.BLOCK


def test_temporal_connection_failure_is_contained_to_the_opt_in_backend():
    from adjacency.temporal_hitl import (
        TemporalHITLError,
        TemporalHITLQueue,
        TemporalSettings,
    )

    async def unavailable(*args, **kwargs):
        raise OSError("service unavailable")

    async def scenario() -> None:
        settings = TemporalSettings(
            address="unreachable.invalid:7233",
            namespace="test",
            api_key="secret-value",
        )
        assert "secret-value" not in repr(settings)
        with pytest.raises(TemporalHITLError, match="explicitly selected"):
            await TemporalHITLQueue.connect(settings=settings, connector=unavailable)

    asyncio.run(scenario())
