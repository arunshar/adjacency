from __future__ import annotations

import json
from pathlib import Path

import pytest

from adjacency.baseline import MAX_BLOCKLIST_TERMS, KeywordExpander
from adjacency.fixtures import FixtureStore
from adjacency.gates import g0_source_spans
from adjacency.policy import PolicyCompiler
from adjacency.xai import RecordedXAIClient

pytestmark = pytest.mark.integration


def test_compiler_and_expander_replay_the_recorded_demo_without_network():
    root = Path(__file__).resolve().parents[1]
    demo = json.loads((root / "examples" / "demo_policy.json").read_text(encoding="utf-8"))
    client = RecordedXAIClient(
        FixtureStore(root / "fixtures" / "api", record=False),
        transport=lambda _request: pytest.fail("fixture replay attempted a live call"),
    )

    spec = PolicyCompiler(client).compile(
        advertiser=demo["advertiser"],
        prose=demo["prose"],
        version=demo["version"],
    )
    blocklist = KeywordExpander(client).expand(spec)

    assert all(result.passed for result in g0_source_spans(spec))
    assert blocklist.source_prose == spec.prose
    assert blocklist.policy_hash == spec.policy_hash
    assert 0 < len(blocklist.terms) <= MAX_BLOCKLIST_TERMS
