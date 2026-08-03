#!/usr/bin/env python3
"""Build the artifact-backed snapshot consumed by the Autopsy UI."""

from __future__ import annotations

import json
from pathlib import Path

from adjacency.autopsy import AutopsyDemo, GatePhase, load_autopsy_bundle

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "artifacts" / "ui" / "autopsy_snapshot.json"


def main() -> None:
    bundle = load_autopsy_bundle(ROOT)
    demo = AutopsyDemo(bundle)
    final_frame = demo.frames()[-1]
    if final_frame.gate_phase is not GatePhase.FAILED:
        raise RuntimeError("final Autopsy frame did not execute the gate-fail beat")
    final_view = demo.view(final_frame)
    wow = bundle.record(bundle.wow_item_id)
    recovered_value = (
        len(final_view.over_block) * bundle.economics.default_value_per_recovered_item_usd
    )
    payload = {
        "corpus_hash": bundle.corpus_hash,
        "delta_distribution": bundle.final_delta_counts,
        "delta_semantics": "BLOCK and REVIEW both withhold immediate delivery",
        "demo_mode_default": True,
        "economics": {
            "counter_value_usd": format(recovered_value, ".2f"),
            "evidence_class": bundle.economics.evidence_class,
            "value_per_recovered_item_usd": format(
                bundle.economics.default_value_per_recovered_item_usd,
                ".2f",
            ),
        },
        "gate_fail_beat": {
            "after_action": wow.trace.final_verdict.action.value,
            "before_action": wow.pre_gate_action.value,
            "code": "G1_SPAN_NOT_FOUND",
            "item_id": wow.item.item_id,
        },
        "hitl_item_count": len(final_view.hitl),
        "policy_hash": bundle.policy_hash,
        "schema_version": 1,
        "source_artifacts": [
            "artifacts/tuesday/baseline_blocklist.json",
            "artifacts/ui/economics_assumption.json",
            "artifacts/wednesday/judge_traces.json",
            "corpus/frozen/manifest.json",
        ],
    }
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
