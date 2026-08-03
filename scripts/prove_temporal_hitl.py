#!/usr/bin/env python3
"""Run one live Temporal HITL transition and record a credential-free artifact."""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import temporalio
from temporalio.worker import Worker

from adjacency.autopsy import load_autopsy_bundle
from adjacency.hitl import Adjudication, HumanAction, ReviewRequest
from adjacency.temporal_hitl import (
    QUERY_NAME,
    SIGNAL_NAME,
    WORKFLOW_NAME,
    HITLReviewWorkflow,
    TemporalHITLQueue,
    TemporalSettings,
)

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = ROOT / "artifacts" / "temporal" / "hitl_live_proof.json"


async def main() -> None:
    settings = TemporalSettings.from_env()
    bundle = load_autopsy_bundle(ROOT)
    record = bundle.record(bundle.wow_item_id)
    request = ReviewRequest(
        request_id=f"temporal-live-proof-{uuid.uuid4().hex}",
        trace_id=record.trace_id,
        item_id=record.item.item_id,
        policy_hash=bundle.policy_hash,
        corpus_hash=bundle.corpus_hash,
        reason_codes=record.trace.failed_gate_codes,
        source_url=record.source_url,
    )
    adjudication = Adjudication(
        request_id=request.request_id,
        action=HumanAction.ALLOW,
        adjudicator="integration-proof",
        note="Protocol proof only. This is not a human label.",
    )
    queue = await TemporalHITLQueue.connect(settings=settings)
    async with Worker(
        queue.client,
        task_queue=queue.task_queue,
        workflows=[HITLReviewWorkflow],
    ):
        enqueued = await queue.enqueue(request)
        queried_before = await queue.state(request.request_id)
        adjudicated = await queue.adjudicate(request.request_id, adjudication)
        queried_after = await queue.state(request.request_id)
        handle = queue.client.get_workflow_handle_for(
            HITLReviewWorkflow.run,
            queue.workflow_id(request.request_id),
        )
        description = await handle.describe()

    if enqueued != queried_before or adjudicated != queried_after:
        raise RuntimeError("Temporal query did not reproduce the workflow state")

    payload = {
        "credential_fields_recorded": [],
        "execution": {
            "closed_at": description.close_time.isoformat() if description.close_time else None,
            "run_id": description.run_id,
            "started_at": description.start_time.isoformat(),
            "status": description.status.name,
        },
        "namespace_sha256": hashlib.sha256(settings.namespace.encode("utf-8")).hexdigest(),
        "query_name": QUERY_NAME,
        "recorded_at": datetime.now(UTC).isoformat(),
        "schema_version": 1,
        "sdk_version": temporalio.__version__,
        "signal_name": SIGNAL_NAME,
        "source_artifacts": [
            "artifacts/ui/autopsy_snapshot.json",
            "artifacts/wednesday/judge_traces.json",
            "corpus/frozen/manifest.json",
        ],
        "state_after": asdict(queried_after),
        "state_before": asdict(queried_before),
        "task_queue": queue.task_queue,
        "workflow_id": queue.workflow_id(request.request_id),
        "workflow_name": WORKFLOW_NAME,
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "artifact": str(ARTIFACT_PATH.relative_to(ROOT)),
                "state_after": queried_after.status,
                "state_before": queried_before.status,
                "workflow_id": payload["workflow_id"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
