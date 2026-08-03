from __future__ import annotations

import json
from pathlib import Path

import pytest

from adjacency.baseline import BaselineBlocklist, BaselineMatcher
from adjacency.contracts import PolicySpec, Verdict
from adjacency.corpus import load_frozen_corpus
from adjacency.fixtures import FixtureStore
from adjacency.inventory import InventoryFetcher, InventorySearch, XStatusResolver
from adjacency.judge import AdjacencyJudge
from adjacency.prompt_baseline import RawPromptBaseline, compare_raw_prompt_runs
from adjacency.xai import RecordedXAIClient

pytestmark = pytest.mark.integration


def test_wednesday_recordings_replay_end_to_end_without_network():
    root = Path(__file__).resolve().parents[1]
    fixtures = FixtureStore(root / "fixtures" / "api", record=False)
    client = RecordedXAIClient(
        fixtures,
        transport=lambda _request: pytest.fail("fixture replay attempted a live model call"),
    )
    corpus = load_frozen_corpus(
        root / "corpus" / "frozen" / "manifest.json",
        verify_media_root=root,
    )
    discovery = _read(root / "artifacts" / "wednesday" / "inventory_discovery.json")
    first_search = discovery["fetch_records"][0]["search"]
    fetched = InventoryFetcher(client).fetch(InventorySearch(**first_search))
    assert [post.model_dump(mode="json") for post in fetched.posts] == discovery["fetch_records"][
        0
    ]["posts"]

    first_record = corpus.records[0]
    resolved = XStatusResolver(
        fixtures,
        transport=lambda _url: pytest.fail("fixture replay attempted live X metadata"),
    ).resolve(first_record.source_url)
    assert resolved.text == first_record.item.text

    policy_document = _read(root / "artifacts" / "tuesday" / "policy_spec.json")
    blocklist_document = _read(root / "artifacts" / "tuesday" / "baseline_blocklist.json")
    spec = PolicySpec.model_validate(policy_document["policy_spec"])
    blocklist = BaselineBlocklist.model_validate(blocklist_document["baseline_blocklist"])
    traces_document = _read(root / "artifacts" / "wednesday" / "judge_traces.json")
    expected_trace = next(
        trace for trace in traces_document["traces"] if trace["final_verdict"]["tier"] == 1
    )
    item = next(item for item in corpus.items if item.item_id == expected_trace["item_id"])
    replayed_trace = AdjacencyJudge(
        client,
        spec,
        BaselineMatcher(blocklist),
        media_root=root,
    ).judge(item)
    assert replayed_trace.verdict == Verdict.model_validate(expected_trace["final_verdict"])

    raw = RawPromptBaseline(client, media_root=root)
    first = raw.run(corpus, policy_prose=spec.prose, run_number=1)
    second = raw.run(corpus, policy_prose=spec.prose, run_number=2)
    comparison = compare_raw_prompt_runs(corpus, first, second)
    committed_comparison = _read(root / "evals" / "prompt_baseline" / "comparison.json")
    assert (
        comparison["action_disagreement_item_ids"]
        == committed_comparison["action_disagreement_item_ids"]
    )
    assert comparison["run_1"] == committed_comparison["run_1"]
    assert comparison["run_2"] == committed_comparison["run_2"]


def _read(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected an object at {path}")
    return value
