#!/usr/bin/env python3
"""Record or replay Tuesday model calls and build their derived artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from adjacency.baseline import KEYWORD_EXPANDER_SURFACE, KeywordExpander
from adjacency.contracts import (
    SEVERITY_ACTION,
    InventoryItem,
    PolicySpec,
    TextEvidence,
    Verdict,
)
from adjacency.fixtures import FixtureStore
from adjacency.gates import run_verdict_gates
from adjacency.policy import POLICY_COMPILER_SURFACE, PolicyCompiler
from adjacency.synthetic_faults import (
    KnownGoodCase,
    evaluate_synthetic_faults,
    inject_synthetic_faults,
)
from adjacency.xai import RecordedXAIClient

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = ROOT / "artifacts" / "tuesday"
SEED = 20260804


def main() -> None:
    demo = json.loads((ROOT / "examples" / "demo_policy.json").read_text(encoding="utf-8"))
    fixture_store = FixtureStore(ROOT / "fixtures" / "api")
    client = RecordedXAIClient(fixture_store)

    spec = PolicyCompiler(client).compile(
        advertiser=demo["advertiser"],
        prose=demo["prose"],
        version=demo["version"],
    )
    blocklist = KeywordExpander(client).expand(spec)
    known_good = _known_good_cases(spec)
    report = evaluate_synthetic_faults(known_good, spec, seed=SEED)
    faults = inject_synthetic_faults(known_good, spec, seed=SEED)

    policy_path = ARTIFACT_ROOT / "policy_spec.json"
    blocklist_path = ARTIFACT_ROOT / "baseline_blocklist.json"
    faults_path = ARTIFACT_ROOT / "synthetic_faults.json"
    _write_json(
        policy_path,
        {
            "artifact_type": "compiled_policy",
            "compiler": {
                "model": "grok-4.5",
                "reasoning_effort": "high",
                "surface": POLICY_COMPILER_SURFACE,
            },
            "policy_hash": spec.policy_hash,
            "policy_spec": spec.model_dump(mode="json"),
        },
    )
    _write_json(
        blocklist_path,
        {
            "artifact_type": "arun_keyword_blocklist_baseline",
            "baseline_blocklist": blocklist.model_dump(mode="json"),
            "baseline_hash": blocklist.baseline_hash,
            "disclosure": (
                "This comparison baseline is Arun's construction, not X's internal blocklist."
            ),
            "generator": {
                "model": "grok-4.5",
                "reasoning_effort": "low",
                "surface": KEYWORD_EXPANDER_SURFACE,
            },
            "source_policy_hash": spec.policy_hash,
        },
    )
    _write_json(
        faults_path,
        {
            "artifact_type": "synthetic_gate_fault_evaluation",
            "clean_cases": [
                {
                    "gate_codes": list(run_verdict_gates(case.verdict, case.item, spec).codes),
                    "item_id": case.item.item_id,
                }
                for case in known_good
            ],
            "fault_cases": [
                {
                    "caught": fault.expected_gate_code
                    in run_verdict_gates(fault.verdict, fault.item, spec).codes,
                    "expected_gate_code": fault.expected_gate_code,
                    "fault_kind": fault.kind.value,
                    "item_id": fault.source_item_id,
                    "observed_gate_codes": list(
                        run_verdict_gates(fault.verdict, fault.item, spec).codes
                    ),
                }
                for fault in faults
            ],
            "report": report.as_dict(),
        },
    )

    print(
        json.dumps(
            {
                "artifacts": [
                    str(policy_path.relative_to(ROOT)),
                    str(blocklist_path.relative_to(ROOT)),
                    str(faults_path.relative_to(ROOT)),
                ],
                "baseline_hash": blocklist.baseline_hash,
                "policy_hash": spec.policy_hash,
                "report": report.as_dict(),
            },
            indent=2,
            sort_keys=True,
        )
    )


def _known_good_cases(spec: PolicySpec) -> tuple[KnownGoodCase, ...]:
    cases: list[KnownGoodCase] = []
    for index, clause in enumerate(spec.clauses, start=1):
        prefix = "Policy evaluation context: "
        text = f"{prefix}{clause.source_text}"
        item = InventoryItem(item_id=f"synthetic-clean-{index}", text=text)
        evidence = TextEvidence(
            quote=clause.source_text,
            start=len(prefix),
            end=len(prefix) + len(clause.source_text),
        )
        verdict = Verdict(
            item_id=item.item_id,
            action=SEVERITY_ACTION[clause.severity],
            severity=clause.severity,
            clause_ids=(clause.clause_id,),
            evidence=(evidence,),
            confidence=0.99,
            tier=1,
            rationale="Known-good verdict generated from the grounded policy clause.",
            policy_version=spec.version,
        )
        cases.append(KnownGoodCase(item=item, verdict=verdict))
    return tuple(cases)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
