from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from adjacency.imagine_signal.canonical import content_sha256

pytestmark = pytest.mark.integration


def test_committed_demo_artifact_matches_fresh_offline_replay() -> None:
    artifact_path = Path("artifacts/imagine_signal/offline_demo.json")
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "scripts/run_imagine_signal_demo.py", "--print"],
        check=True,
        capture_output=True,
        text=True,
    )
    committed = json.loads(artifact_path.read_text(encoding="utf-8"))
    rebuilt = json.loads(completed.stdout)

    assert committed == rebuilt
    unsigned = dict(committed)
    digest = unsigned.pop("artifact_sha256")
    assert content_sha256(unsigned) == digest
    assert rebuilt["network_used"] is False
    assert rebuilt["provider_call_used"] is False
    assert rebuilt["x_ads_write_client_present"] is False
    assert rebuilt["production_authorization"] == "NOT_PRESENT"


def test_demo_artifact_contains_only_labeled_nonproduction_evidence() -> None:
    artifact = json.loads(
        Path("artifacts/imagine_signal/offline_demo.json").read_text(encoding="utf-8")
    )

    assert artifact["evidence_labels"] == {
        "assets": "FROZEN_REPLAY_SYNTHETIC_FIXTURE",
        "auction": "E2_SIMULATED",
        "outcomes": "FROZEN_REPLAY_SYNTHETIC_AGGREGATES",
    }
    assert artifact["decision"]["final_action"] == "TEST"
    assert all(item["passed"] for item in artifact["decision"]["gate_results"])
    assert "The variant increases X revenue." in artifact["prohibited_claims"]
