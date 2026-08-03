"""Seeded fault injection for measuring deterministic gate behavior."""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from adjacency.contracts import (
    SEVERITY_ACTION,
    InventoryItem,
    PolicySpec,
    TextEvidence,
    Verdict,
)
from adjacency.gates import run_verdict_gates


class FaultKind(StrEnum):
    HALLUCINATED_SPAN = "hallucinated_span"
    SEVERITY_MISMATCH = "severity_mismatch"
    INVENTED_CLAUSE_ID = "invented_clause_id"


EXPECTED_GATE_CODE = {
    FaultKind.HALLUCINATED_SPAN: "G1_SPAN_NOT_FOUND",
    FaultKind.SEVERITY_MISMATCH: "G4_SEVERITY_INCOHERENT",
    FaultKind.INVENTED_CLAUSE_ID: "G2_CLAUSE_NOT_FOUND",
}


@dataclass(frozen=True, slots=True)
class KnownGoodCase:
    item: InventoryItem
    verdict: Verdict


@dataclass(frozen=True, slots=True)
class SyntheticFaultCase:
    source_item_id: str
    kind: FaultKind
    item: InventoryItem
    verdict: Verdict
    expected_gate_code: str


@dataclass(frozen=True, slots=True)
class FaultDetection:
    kind: FaultKind
    injected: int
    caught: int

    @property
    def catch_rate(self) -> float:
        return self.caught / self.injected


@dataclass(frozen=True, slots=True)
class SyntheticFaultReport:
    seed: int
    policy_hash: str
    clean_total: int
    clean_rejected: int
    injected_total: int
    injected_caught: int
    by_fault: tuple[FaultDetection, ...]

    @property
    def catch_rate(self) -> float:
        return self.injected_caught / self.injected_total

    @property
    def false_positive_rate(self) -> float:
        return self.clean_rejected / self.clean_total

    def as_dict(self) -> dict[str, object]:
        return {
            "by_fault": [
                {
                    "catch_rate": result.catch_rate,
                    "caught": result.caught,
                    "injected": result.injected,
                    "kind": result.kind.value,
                }
                for result in self.by_fault
            ],
            "catch_rate": self.catch_rate,
            "clean_rejected": self.clean_rejected,
            "clean_total": self.clean_total,
            "false_positive_rate": self.false_positive_rate,
            "injected_caught": self.injected_caught,
            "injected_total": self.injected_total,
            "policy_hash": self.policy_hash,
            "seed": self.seed,
        }


class SyntheticFaultError(ValueError):
    """Raised when a source case cannot support isolated fault injection."""


def inject_synthetic_faults(
    cases: tuple[KnownGoodCase, ...],
    spec: PolicySpec,
    *,
    seed: int,
) -> tuple[SyntheticFaultCase, ...]:
    """Create each supported fault for every clean case, then seed the order."""

    if not cases:
        raise SyntheticFaultError("at least one known-good case is required")

    missing_clause_id = "__synthetic_missing_clause__"
    while missing_clause_id in spec.clause_ids:
        missing_clause_id += "_x"

    faults: list[SyntheticFaultCase] = []
    for case in cases:
        if case.item.item_id != case.verdict.item_id:
            raise SyntheticFaultError("item and verdict ids must match")
        text_index = next(
            (
                index
                for index, evidence in enumerate(case.verdict.evidence)
                if isinstance(evidence, TextEvidence)
            ),
            None,
        )
        if text_index is None:
            raise SyntheticFaultError("hallucinated-span injection requires text evidence")

        text_evidence = cast(TextEvidence, case.verdict.evidence[text_index])
        replacement_quote = _different_quote(text_evidence.quote)
        replaced_evidence = list(case.verdict.evidence)
        replaced_evidence[text_index] = text_evidence.model_copy(
            update={"quote": replacement_quote}
        )
        hallucinated = _validated_copy(
            case.verdict,
            evidence=tuple(replaced_evidence),
        )
        faults.append(_fault_case(case, FaultKind.HALLUCINATED_SPAN, hallucinated))

        mismatched_severity = next(
            severity
            for severity, action in SEVERITY_ACTION.items()
            if action is not case.verdict.action
        )
        mismatch = _validated_copy(case.verdict, severity=mismatched_severity)
        faults.append(_fault_case(case, FaultKind.SEVERITY_MISMATCH, mismatch))

        invented = _validated_copy(
            case.verdict,
            clause_ids=(*case.verdict.clause_ids, missing_clause_id),
        )
        faults.append(_fault_case(case, FaultKind.INVENTED_CLAUSE_ID, invented))

    # This is deterministic evaluation ordering, not security randomness.
    random.Random(seed).shuffle(faults)  # nosec B311
    return tuple(faults)


def evaluate_synthetic_faults(
    cases: tuple[KnownGoodCase, ...],
    spec: PolicySpec,
    *,
    seed: int,
) -> SyntheticFaultReport:
    """Measure expected-gate catches and clean-case false positives."""

    if not cases:
        raise SyntheticFaultError("at least one known-good case is required")

    clean_rejected = sum(
        not run_verdict_gates(case.verdict, case.item, spec).passed for case in cases
    )
    faults = inject_synthetic_faults(cases, spec, seed=seed)
    counts = {kind: [0, 0] for kind in FaultKind}
    for fault in faults:
        result = run_verdict_gates(fault.verdict, fault.item, spec)
        counts[fault.kind][0] += 1
        if fault.expected_gate_code in result.codes:
            counts[fault.kind][1] += 1

    by_fault = tuple(
        FaultDetection(kind=kind, injected=counts[kind][0], caught=counts[kind][1])
        for kind in FaultKind
    )
    injected_total = len(faults)
    injected_caught = sum(result.caught for result in by_fault)
    return SyntheticFaultReport(
        seed=seed,
        policy_hash=spec.policy_hash,
        clean_total=len(cases),
        clean_rejected=clean_rejected,
        injected_total=injected_total,
        injected_caught=injected_caught,
        by_fault=by_fault,
    )


def _fault_case(
    source: KnownGoodCase,
    kind: FaultKind,
    verdict: Verdict,
) -> SyntheticFaultCase:
    return SyntheticFaultCase(
        source_item_id=source.item.item_id,
        kind=kind,
        item=source.item,
        verdict=verdict,
        expected_gate_code=EXPECTED_GATE_CODE[kind],
    )


def _different_quote(original: str) -> str:
    marker = "¤" if original != "¤" * len(original) else "§"
    return marker * len(original)


def _validated_copy(verdict: Verdict, **changes: object) -> Verdict:
    payload = verdict.model_dump()
    payload.update(changes)
    return Verdict.model_validate(payload)
