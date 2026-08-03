from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest

from adjacency.baseline import BaselineBlocklist, BaselineMatcher
from adjacency.contracts import Action, InventoryItem, Media, Verdict
from adjacency.judge import AdjacencyJudge, EscalationReason, summarize_judge_run
from adjacency.near_dup import NearDupGroup

pytestmark = pytest.mark.unit


def response_for(verdict: Verdict) -> dict[str, object]:
    return {
        "id": f"response-{verdict.item_id}-{verdict.tier}",
        "model": "grok-4.5",
        "output": [
            {
                "content": [
                    {
                        "text": json.dumps(verdict.model_dump(mode="json")),
                        "type": "output_text",
                    }
                ],
                "type": "message",
            }
        ],
        "status": "completed",
        "usage": {
            "cost_in_usd_ticks": 100,
            "input_tokens": 10,
            "output_tokens": 5,
            "output_tokens_details": {"reasoning_tokens": 2},
            "total_tokens": 15,
        },
    }


def verdict(
    item_id: str,
    *,
    action: Action,
    severity: int,
    confidence: float,
    tier: int,
) -> Verdict:
    return Verdict(
        item_id=item_id,
        action=action,
        severity=severity,
        confidence=confidence,
        tier=tier,
        policy_version=1,
    )


class StubClient:
    def __init__(self, responses: list[Mapping[str, Any]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, Mapping[str, Any]]] = []

    def create(self, *, surface: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.calls.append((surface, payload))
        if not self.responses:
            pytest.fail("unexpected model call")
        return self.responses.pop(0)


def matcher(spec) -> BaselineMatcher:
    return BaselineMatcher(
        BaselineBlocklist(
            advertiser=spec.advertiser,
            policy_version=spec.version,
            policy_hash=spec.policy_hash,
            source_prose=spec.prose,
            terms=("violence",),
        )
    )


def test_tier_zero_returns_without_a_model_call(spec):
    client = StubClient([])
    judge = AdjacencyJudge(client, spec, matcher(spec))

    trace = judge.judge(InventoryItem(item_id="clean", text="A weather update."))

    assert trace.verdict.action is Action.ALLOW
    assert trace.verdict.tier == 0
    assert trace.model_calls == ()
    assert client.calls == []


def test_clean_text_with_media_escalates_from_low_to_high(spec, tmp_path):
    image = tmp_path / "image.jpg"
    image.write_bytes(b"fixture-image")
    item = InventoryItem(
        item_id="media",
        text="A weather update.",
        media=(
            Media(
                media_id="m1",
                kind="image",
                width=10,
                height=10,
                local_path="image.jpg",
            ),
        ),
    )
    client = StubClient(
        [
            response_for(
                verdict(item.item_id, action=Action.ALLOW, severity=0, confidence=0.95, tier=1)
            ),
            response_for(
                verdict(item.item_id, action=Action.ALLOW, severity=1, confidence=0.95, tier=2)
            ),
        ]
    )

    trace = AdjacencyJudge(client, spec, matcher(spec), media_root=tmp_path).judge(item)

    assert trace.verdict.tier == 2
    assert EscalationReason.MEDIA_WITH_CLEAN_TEXT in trace.escalation_reasons
    assert len(trace.model_calls) == 2
    content = client.calls[0][1]["input"][0]["content"]
    assert any(part.get("type") == "input_image" for part in content)
    assert client.calls[0][1]["reasoning"] == {"effort": "low"}
    assert client.calls[1][1]["reasoning"] == {"effort": "high"}


@pytest.mark.parametrize(
    ("low", "reason"),
    (
        (
            verdict("risk", action=Action.BLOCK, severity=3, confidence=0.2, tier=1),
            EscalationReason.LOW_CONFIDENCE,
        ),
        (
            verdict("risk", action=Action.REVIEW, severity=2, confidence=0.9, tier=1),
            EscalationReason.BOUNDARY_SEVERITY,
        ),
        (
            verdict("risk", action=Action.ALLOW, severity=4, confidence=0.9, tier=1),
            EscalationReason.LOW_TIER_GATE_FAILURE,
        ),
    ),
)
def test_low_tier_escalation_predicates(spec, low, reason):
    item = InventoryItem(item_id="risk", text="A report about violence.")
    high = verdict("risk", action=Action.BLOCK, severity=4, confidence=0.95, tier=2)
    trace = AdjacencyJudge(
        StubClient([response_for(low), response_for(high)]),
        spec,
        matcher(spec),
    ).judge(item)

    assert reason in trace.escalation_reasons
    assert trace.verdict.tier == 2


def test_invalid_model_outputs_fail_closed_to_review(spec):
    invalid = {"output": [], "status": "completed"}
    item = InventoryItem(item_id="risk", text="violence")

    trace = AdjacencyJudge(
        StubClient([invalid, invalid]),
        spec,
        matcher(spec),
    ).judge(item)

    assert trace.verdict.action is Action.REVIEW
    assert trace.verdict.tier == 2
    assert EscalationReason.MODEL_FAILURE in trace.escalation_reasons
    assert len(trace.model_errors) == 2


def test_near_duplicate_action_disagreement_forces_high_effort(spec):
    first = InventoryItem(item_id="a", text="violence report alpha")
    second = InventoryItem(item_id="b", text="violence report beta")
    responses = [
        response_for(verdict("a", action=Action.ALLOW, severity=0, confidence=0.9, tier=1)),
        response_for(verdict("b", action=Action.BLOCK, severity=4, confidence=0.9, tier=1)),
        response_for(verdict("a", action=Action.ALLOW, severity=1, confidence=0.9, tier=2)),
        response_for(verdict("b", action=Action.BLOCK, severity=4, confidence=0.9, tier=2)),
    ]
    judge = AdjacencyJudge(StubClient(responses), spec, matcher(spec))

    traces = judge.judge_all(
        (first, second),
        near_dup_groups=(NearDupGroup(cluster_id="cluster", item_ids=("a", "b")),),
    )

    assert all(trace.verdict.tier == 2 for trace in traces)
    assert all(
        EscalationReason.CLUSTER_DISAGREEMENT in trace.escalation_reasons for trace in traces
    )


def test_judge_summary_reports_fail_closed_gate_counts(spec):
    item = InventoryItem(item_id="risk", text="A report about violence.")
    invalid_low = verdict("risk", action=Action.ALLOW, severity=4, confidence=0.9, tier=1)
    invalid_high = verdict("risk", action=Action.ALLOW, severity=4, confidence=0.9, tier=2)
    trace = AdjacencyJudge(
        StubClient([response_for(invalid_low), response_for(invalid_high)]),
        spec,
        matcher(spec),
    ).judge(item)

    report = summarize_judge_run((trace,), corpus_hash="corpus-hash")

    assert report["items_with_gate_failures"] == 1
    assert report["gate_failure_code_counts"] == {"G4_SEVERITY_INCOHERENT": 1}
