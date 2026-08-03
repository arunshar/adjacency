#!/usr/bin/env python3
"""Verify the evidence values used by the frozen paper, deck, and results sheet."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def read_json(relative_path: str) -> dict[str, Any]:
    value = json.loads((ROOT / relative_path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"expected object in {relative_path}")
    return value


def main() -> None:
    faults = read_json("artifacts/tuesday/synthetic_faults.json")["report"]
    assert faults["injected_caught"] == faults["injected_total"] == 12
    assert faults["clean_rejected"] == 0
    assert faults["clean_total"] == 4

    prompt = read_json("evals/prompt_baseline/comparison.json")
    assert prompt["run_1"]["grounding"]["failure_rate"] == 0.68
    assert prompt["action_disagreement_rate"] == 0.02

    judge = read_json("artifacts/wednesday/judge_report.json")
    assert judge["tier_distribution"]["2"]["fraction"] == 0.44
    assert round(judge["blended_cost_per_1000_decisions_usd"], 2) == 6.12

    temporal = read_json("artifacts/temporal/hitl_live_proof.json")
    assert temporal["workflow_name"] == "AdjacencyHITLReview"
    assert temporal["signal_name"] == "adjudicate"
    assert temporal["query_name"] == "queue_state"
    assert temporal["state_before"]["status"] == "PENDING"
    assert temporal["state_after"]["status"] == "ADJUDICATED"
    assert temporal["execution"]["status"] == "COMPLETED"
    assert temporal["credential_fields_recorded"] == []

    video_meta = read_json("artifacts/demo/adjacency_fallback.json")
    video_path = ROOT / video_meta["artifact"]
    assert video_path.stat().st_size == video_meta["file_size_bytes"]
    assert hashlib.sha256(video_path.read_bytes()).hexdigest() == video_meta["sha256"]
    assert video_meta["network_credentials_present"] is False

    print("release artifacts verified")
    print("synthetic faults: 12/12 caught, 0/4 clean rejected")
    print("raw prompt: 68% grounding failure, 2% action disagreement")
    print("judge: 44% Tier 2, $6.12 per 1,000 decisions")
    print("Temporal: PENDING to ADJUDICATED to COMPLETED")
    print(f"fallback video: {video_meta['sha256']}")


if __name__ == "__main__":
    main()
