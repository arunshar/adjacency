"""HITL queue contracts and the dependency-free in-process backend."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Protocol

DEFAULT_HITL_BACKEND = "in_process"
TEMPORAL_HITL_BACKEND = "temporal"


class HITLQueueError(ValueError):
    """Raised when a review queue request is invalid or unavailable."""


class ReviewStatus(StrEnum):
    PENDING = "PENDING"
    ADJUDICATED = "ADJUDICATED"


class HumanAction(StrEnum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"


@dataclass(frozen=True, slots=True)
class ReviewRequest:
    request_id: str
    trace_id: str
    item_id: str
    policy_hash: str
    corpus_hash: str
    reason_codes: tuple[str, ...]
    source_url: str
    proposed_action: str = "REVIEW"
    schema_version: int = 1

    def __post_init__(self) -> None:
        _require_text("request_id", self.request_id)
        _require_text("trace_id", self.trace_id)
        _require_text("item_id", self.item_id)
        _require_text("policy_hash", self.policy_hash)
        _require_text("corpus_hash", self.corpus_hash)
        _require_text("source_url", self.source_url)
        if not self.reason_codes or any(not value.strip() for value in self.reason_codes):
            raise HITLQueueError("reason_codes must contain nonempty values")
        if self.proposed_action != "REVIEW":
            raise HITLQueueError("HITL requests must enter with action REVIEW")
        if self.schema_version != 1:
            raise HITLQueueError("unsupported review request schema version")


@dataclass(frozen=True, slots=True)
class Adjudication:
    request_id: str
    action: HumanAction
    adjudicator: str
    note: str = ""

    def __post_init__(self) -> None:
        _require_text("request_id", self.request_id)
        _require_text("adjudicator", self.adjudicator)


@dataclass(frozen=True, slots=True)
class ReviewState:
    request: ReviewRequest
    status: ReviewStatus = ReviewStatus.PENDING
    adjudication: Adjudication | None = None
    signal_error: str | None = None


class HITLQueue(Protocol):
    async def enqueue(self, request: ReviewRequest) -> ReviewState: ...

    async def adjudicate(
        self,
        request_id: str,
        adjudication: Adjudication,
    ) -> ReviewState: ...

    async def state(self, request_id: str) -> ReviewState: ...


class InProcessHITLQueue:
    """Process-local queue used by default and safe for the offline demo."""

    def __init__(self) -> None:
        self._states: dict[str, ReviewState] = {}

    async def enqueue(self, request: ReviewRequest) -> ReviewState:
        existing = self._states.get(request.request_id)
        if existing is not None:
            if existing.request != request:
                raise HITLQueueError("request_id already belongs to a different review")
            return existing
        state = ReviewState(request=request)
        self._states[request.request_id] = state
        return state

    async def adjudicate(
        self,
        request_id: str,
        adjudication: Adjudication,
    ) -> ReviewState:
        state = await self.state(request_id)
        updated = apply_adjudication(state, adjudication)
        self._states[request_id] = updated
        return updated

    async def state(self, request_id: str) -> ReviewState:
        try:
            return self._states[request_id]
        except KeyError as error:
            raise HITLQueueError(f"unknown review request: {request_id}") from error


def apply_adjudication(state: ReviewState, adjudication: Adjudication) -> ReviewState:
    """Apply one human decision with idempotency for exact retries."""

    if adjudication.request_id != state.request.request_id:
        raise HITLQueueError("adjudication request_id does not match the review")
    if state.status is ReviewStatus.ADJUDICATED:
        if state.adjudication == adjudication:
            return state
        raise HITLQueueError("review has already been adjudicated")
    return replace(
        state,
        status=ReviewStatus.ADJUDICATED,
        adjudication=adjudication,
        signal_error=None,
    )


def hitl_backend_name(environ: Mapping[str, str] | None = None) -> str:
    source = os.environ if environ is None else environ
    name = source.get("ADJ_HITL_BACKEND", DEFAULT_HITL_BACKEND).strip().lower()
    if name not in {DEFAULT_HITL_BACKEND, TEMPORAL_HITL_BACKEND}:
        raise HITLQueueError("ADJ_HITL_BACKEND must be either in_process or temporal")
    return name


async def create_hitl_queue(
    backend: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> HITLQueue:
    """Create the selected queue without importing Temporal on the default path."""

    name = backend.strip().lower() if backend is not None else hitl_backend_name(environ)
    if name == DEFAULT_HITL_BACKEND:
        return InProcessHITLQueue()
    if name != TEMPORAL_HITL_BACKEND:
        raise HITLQueueError("unsupported HITL backend")
    from adjacency.temporal_hitl import TemporalHITLQueue

    return await TemporalHITLQueue.connect(environ=environ)


def _require_text(field: str, value: str) -> None:
    if not value.strip():
        raise HITLQueueError(f"{field} must be nonempty")
