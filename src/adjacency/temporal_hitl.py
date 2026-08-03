"""Opt-in Temporal backend for the Adjacency human-review queue."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from temporalio import workflow
from temporalio.client import Client
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from adjacency.hitl import (
    Adjudication,
    HITLQueueError,
    ReviewRequest,
    ReviewState,
    ReviewStatus,
    apply_adjudication,
)

TASK_QUEUE = "adjacency-hitl-v1"
WORKFLOW_NAME = "AdjacencyHITLReview"
SIGNAL_NAME = "adjudicate"
QUERY_NAME = "queue_state"


class TemporalHITLError(RuntimeError):
    """Raised when the explicitly selected Temporal backend is unavailable."""


@workflow.defn(name=WORKFLOW_NAME)
class HITLReviewWorkflow:
    """Durably hold one review until a human adjudication signal arrives."""

    @workflow.init
    def __init__(self, request: ReviewRequest) -> None:
        self._state = ReviewState(request=request)

    @workflow.run
    async def run(self, request: ReviewRequest) -> ReviewState:
        await workflow.wait_condition(lambda: self._state.status == ReviewStatus.ADJUDICATED)
        return self._state

    @workflow.signal(name=SIGNAL_NAME)
    def adjudicate(self, adjudication: Adjudication) -> None:
        try:
            self._state = apply_adjudication(self._state, adjudication)
        except HITLQueueError as error:
            self._state = replace(self._state, signal_error=str(error))

    @workflow.query(name=QUERY_NAME)
    def queue_state(self) -> ReviewState:
        return self._state


@dataclass(frozen=True, slots=True)
class TemporalSettings:
    address: str
    namespace: str
    api_key: str = field(repr=False)
    task_queue: str = TASK_QUEUE

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> TemporalSettings:
        source = os.environ if environ is None else environ
        values = {
            name: source.get(name, "").strip()
            for name in (
                "TEMPORAL_ADDRESS",
                "TEMPORAL_NAMESPACE",
                "TEMPORAL_API_KEY",
            )
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise TemporalHITLError("missing Temporal settings: " + ", ".join(sorted(missing)))
        return cls(
            address=values["TEMPORAL_ADDRESS"],
            namespace=values["TEMPORAL_NAMESPACE"],
            api_key=values["TEMPORAL_API_KEY"],
        )


Connector = Callable[..., Awaitable[Any]]


class TemporalHITLQueue:
    """Client adapter for the one-workflow HITL protocol."""

    def __init__(self, client: Any, *, task_queue: str = TASK_QUEUE) -> None:
        self.client = client
        self.task_queue = task_queue

    @classmethod
    async def connect(
        cls,
        *,
        settings: TemporalSettings | None = None,
        environ: Mapping[str, str] | None = None,
        connector: Connector | None = None,
    ) -> TemporalHITLQueue:
        resolved = settings or TemporalSettings.from_env(environ)
        connect = Client.connect if connector is None else connector
        try:
            client = await connect(
                resolved.address,
                namespace=resolved.namespace,
                api_key=resolved.api_key,
                tls=True,
            )
        except Exception as error:
            raise TemporalHITLError(
                "cannot connect to the explicitly selected Temporal HITL backend"
            ) from error
        return cls(client, task_queue=resolved.task_queue)

    async def enqueue(self, request: ReviewRequest) -> ReviewState:
        try:
            handle = await self.client.start_workflow(
                HITLReviewWorkflow.run,
                request,
                id=self.workflow_id(request.request_id),
                task_queue=self.task_queue,
                id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
                id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
                static_summary="Adjacency human review",
            )
        except WorkflowAlreadyStartedError:
            handle = self._handle(request.request_id)
        return await handle.query(HITLReviewWorkflow.queue_state)

    async def adjudicate(
        self,
        request_id: str,
        adjudication: Adjudication,
    ) -> ReviewState:
        if adjudication.request_id != request_id:
            raise HITLQueueError("adjudication request_id does not match the review")
        handle = self._handle(request_id)
        await handle.signal(HITLReviewWorkflow.adjudicate, adjudication)
        return await handle.result()

    async def state(self, request_id: str) -> ReviewState:
        return await self._handle(request_id).query(HITLReviewWorkflow.queue_state)

    @staticmethod
    def workflow_id(request_id: str) -> str:
        digest = hashlib.sha256(request_id.encode("utf-8")).hexdigest()
        return f"adjacency-hitl-{digest}"

    def _handle(self, request_id: str):
        return self.client.get_workflow_handle_for(
            HITLReviewWorkflow.run,
            self.workflow_id(request_id),
        )
