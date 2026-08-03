from __future__ import annotations

from pathlib import Path

import pytest

from adjacency.autopsy import (
    AutopsyDataError,
    AutopsyDemo,
    GatePhase,
    audit_payload,
    load_autopsy_bundle,
)
from adjacency.contracts import Action

pytestmark = pytest.mark.integration


def test_bundled_autopsy_replays_the_three_lanes_and_gate_fail_beat():
    root = Path(__file__).resolve().parents[1]
    bundle = load_autopsy_bundle(root)
    demo = AutopsyDemo(bundle)
    frames = demo.frames()
    pre_gate = next(frame for frame in frames if frame.gate_phase is GatePhase.PRE_GATE)
    failed = frames[frames.index(pre_gate) + 1]
    final = demo.view(frames[-1])

    assert failed.gate_phase is GatePhase.FAILED
    assert bundle.record(bundle.wow_item_id).pre_gate_action is Action.ALLOW
    assert bundle.record(bundle.wow_item_id).trace.final_verdict.action is Action.REVIEW
    assert any(record.item.item_id == bundle.wow_item_id for record in demo.view(pre_gate).agree)
    assert demo.view(failed).gate_fail is not None
    assert sum(bundle.final_delta_counts.values()) == len(bundle.records)
    assert final.agree and final.over_block and final.under_block and final.hitl

    audit = audit_payload(bundle.record(bundle.wow_item_id))
    assert audit["trace_id"] == f"trace:{bundle.wow_item_id}"
    assert [gate["gate"] for gate in audit["gate_chain"]] == ["G1", "G2", "G4", "G6"]
    assert any(
        gate["code"] == "G1_SPAN_NOT_FOUND" and not gate["passed"] for gate in audit["gate_chain"]
    )


def test_autopsy_fails_visibly_when_bundled_artifacts_are_missing(tmp_path):
    with pytest.raises(AutopsyDataError, match="cannot read Autopsy artifact"):
        load_autopsy_bundle(tmp_path)
