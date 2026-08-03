from __future__ import annotations

import pytest

from adjacency.contracts import Action, InventoryItem, TextEvidence, Verdict
from adjacency.synthetic_faults import (
    FaultKind,
    KnownGoodCase,
    SyntheticFaultError,
    evaluate_synthetic_faults,
    inject_synthetic_faults,
)

pytestmark = pytest.mark.unit


def known_good_case() -> KnownGoodCase:
    text = "A post celebrating violence."
    quote = "celebrating violence"
    start = text.index(quote)
    item = InventoryItem(item_id="fault-source", text=text)
    verdict = Verdict(
        item_id=item.item_id,
        action=Action.BLOCK,
        severity=3,
        clause_ids=("C2",),
        evidence=(TextEvidence(quote=quote, start=start, end=start + len(quote)),),
        confidence=0.95,
        tier=1,
        policy_version=1,
    )
    return KnownGoodCase(item=item, verdict=verdict)


def test_all_fault_types_are_seeded_and_caught_by_the_expected_gate(spec):
    cases = (known_good_case(),)

    first = inject_synthetic_faults(cases, spec, seed=20260804)
    second = inject_synthetic_faults(cases, spec, seed=20260804)
    report = evaluate_synthetic_faults(cases, spec, seed=20260804)

    assert [(case.kind, case.source_item_id) for case in first] == [
        (case.kind, case.source_item_id) for case in second
    ]
    assert {case.kind for case in first} == set(FaultKind)
    assert report.clean_total == 1
    assert report.clean_rejected == 0
    assert report.injected_total == 3
    assert report.injected_caught == 3
    assert report.catch_rate == 1.0
    assert report.false_positive_rate == 0.0
    assert all(result.catch_rate == 1.0 for result in report.by_fault)


def test_fault_injection_rejects_empty_or_unusable_source_cases(spec):
    with pytest.raises(SyntheticFaultError, match="at least one"):
        inject_synthetic_faults((), spec, seed=1)

    item = InventoryItem(item_id="no-evidence", text="clean")
    verdict = Verdict(
        item_id=item.item_id,
        action=Action.ALLOW,
        severity=0,
        confidence=1.0,
        policy_version=1,
    )
    with pytest.raises(SyntheticFaultError, match="text evidence"):
        inject_synthetic_faults((KnownGoodCase(item, verdict),), spec, seed=1)
