#!/usr/bin/env python3
"""Run the escalation ladder and two raw-prompt baselines on the frozen corpus."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from adjacency.baseline import BaselineBlocklist, BaselineMatcher
from adjacency.contracts import PolicySpec
from adjacency.corpus import load_frozen_corpus
from adjacency.fixtures import FixtureStore
from adjacency.judge import AdjacencyJudge, JudgeTrace, summarize_judge_run
from adjacency.near_dup import NearDupCluster
from adjacency.prompt_baseline import RawPromptBaseline, compare_raw_prompt_runs
from adjacency.xai import RecordedXAIClient

ROOT = Path(__file__).resolve().parents[1]
CORPUS_MANIFEST = ROOT / "corpus" / "frozen" / "manifest.json"
POLICY_ARTIFACT = ROOT / "artifacts" / "tuesday" / "policy_spec.json"
BLOCKLIST_ARTIFACT = ROOT / "artifacts" / "tuesday" / "baseline_blocklist.json"
JUDGE_TRACES = ROOT / "artifacts" / "wednesday" / "judge_traces.json"
JUDGE_REPORT = ROOT / "artifacts" / "wednesday" / "judge_report.json"
PROMPT_EVAL_ROOT = ROOT / "evals" / "prompt_baseline"


def main() -> None:
    corpus = load_frozen_corpus(CORPUS_MANIFEST, verify_media_root=ROOT)
    policy_document = _read_json(POLICY_ARTIFACT)
    blocklist_document = _read_json(BLOCKLIST_ARTIFACT)
    spec = PolicySpec.model_validate(policy_document["policy_spec"])
    blocklist = BaselineBlocklist.model_validate(blocklist_document["baseline_blocklist"])
    if blocklist.policy_hash != spec.policy_hash:
        raise RuntimeError("baseline and compiled policy hashes differ")

    image_hashes = {
        record.item.item_id: tuple(media.perceptual_hash for media in record.media_records)
        for record in corpus.records
        if record.media_records
    }
    near_dup_groups = NearDupCluster().cluster(corpus.items, image_hashes)
    fixture_store = FixtureStore(ROOT / "fixtures" / "api")
    if fixture_store.record and fixture_store.reuse_existing:
        raise RuntimeError(
            "evaluation recording cannot reuse fixtures because replay latency is not live latency"
        )
    client = RecordedXAIClient(fixture_store)
    judge = AdjacencyJudge(
        client,
        spec,
        BaselineMatcher(blocklist),
        media_root=ROOT,
    )
    traces = judge.judge_all(
        corpus.items,
        near_dup_groups=near_dup_groups,
        max_workers=4,
    )
    report = summarize_judge_run(traces, corpus_hash=corpus.corpus_hash)
    report.update(
        {
            "action_counts": {
                action: sum(trace.verdict.action.value == action for trace in traces)
                for action in ("ALLOW", "REVIEW", "BLOCK")
            },
            "near_duplicate_group_count": len(near_dup_groups),
            "policy_hash": spec.policy_hash,
        }
    )
    _write_or_verify_json(
        JUDGE_TRACES,
        {
            "corpus_hash": corpus.corpus_hash,
            "policy_hash": spec.policy_hash,
            "traces": [_trace_dict(trace) for trace in traces],
        },
        record=fixture_store.record,
    )
    _write_or_verify_json(JUDGE_REPORT, report, record=fixture_store.record)

    raw_baseline = RawPromptBaseline(client, media_root=ROOT)
    first = raw_baseline.run(corpus, policy_prose=spec.prose, run_number=1)
    second = raw_baseline.run(corpus, policy_prose=spec.prose, run_number=2)
    policy_prose_sha256 = hashlib.sha256(spec.prose.encode("utf-8")).hexdigest()
    _write_or_verify_json(
        PROMPT_EVAL_ROOT / "run_1.json",
        {
            "corpus_hash": corpus.corpus_hash,
            "policy_prose_sha256": policy_prose_sha256,
            "run": first.as_dict(),
        },
        record=fixture_store.record,
    )
    _write_or_verify_json(
        PROMPT_EVAL_ROOT / "run_2.json",
        {
            "corpus_hash": corpus.corpus_hash,
            "policy_prose_sha256": policy_prose_sha256,
            "run": second.as_dict(),
        },
        record=fixture_store.record,
    )
    comparison = compare_raw_prompt_runs(corpus, first, second)
    comparison.update(
        {
            "policy_prose_sha256": policy_prose_sha256,
            "run_1_measurement": first.measurement.as_dict(),
            "run_2_measurement": second.measurement.as_dict(),
        }
    )
    _write_or_verify_json(
        PROMPT_EVAL_ROOT / "comparison.json",
        comparison,
        record=fixture_store.record,
    )

    print(
        json.dumps(
            {
                "corpus_hash": corpus.corpus_hash,
                "judge_report": report,
                "raw_prompt_comparison": comparison,
            },
            indent=2,
            sort_keys=True,
        )
    )


def _trace_dict(trace: JudgeTrace) -> dict[str, object]:
    return {
        "escalation_reasons": [reason.value for reason in trace.escalation_reasons],
        "final_verdict": trace.verdict.model_dump(mode="json"),
        "gate_results": [
            {
                "code": result.code,
                "coerce_to": result.coerce_to.value if result.coerce_to else None,
                "detail": result.detail,
                "gate": result.gate,
                "passed": result.passed,
            }
            for result in trace.gate_result.results
        ],
        "item_id": trace.item_id,
        "low_verdict": (trace.low_verdict.model_dump(mode="json") if trace.low_verdict else None),
        "matched_terms": list(trace.matched_terms),
        "model_calls": [call.as_dict() for call in trace.model_calls],
        "model_errors": list(trace.model_errors),
        "tier_zero_code": trace.tier_zero_code.value,
    }


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object at {path}")
    return value


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_or_verify_json(path: Path, payload: object, *, record: bool) -> None:
    if record or not path.exists():
        _write_json(path, payload)
        return
    committed = json.loads(path.read_text(encoding="utf-8"))
    if _without_replay_latency(committed) != _without_replay_latency(payload):
        raise RuntimeError(f"fixture replay changed the committed evaluation artifact: {path}")


def _without_replay_latency(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _without_replay_latency(item)
            for key, item in value.items()
            if key not in {"elapsed_ms", "model_latency_ms"}
        }
    if isinstance(value, list):
        return [_without_replay_latency(item) for item in value]
    return value


if __name__ == "__main__":
    main()
