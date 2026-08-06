"""Evidence ceilings and deterministic action resolution for ImagineSignal."""

from __future__ import annotations

from collections.abc import Sequence

from adjacency.imagine_signal.contracts import (
    DeploymentMode,
    EvidenceClass,
    NextAction,
    SignalDecision,
    SignalGateResult,
)

_EARLY_EVIDENCE = frozenset(
    {
        EvidenceClass.PROPOSED,
        EvidenceClass.IMPLEMENTED,
        EvidenceClass.UNIT_TESTED,
    }
)

_NON_PRODUCTION_ACTIONS = frozenset(
    {
        NextAction.KEEP,
        NextAction.EDIT,
        NextAction.TEST,
        NextAction.HOLD,
        NextAction.REVIEW,
        NextAction.STOP,
    }
)

_RESTRICTIVENESS = {
    NextAction.TEST: 0,
    NextAction.EDIT: 1,
    NextAction.KEEP: 2,
    NextAction.HOLD: 3,
    NextAction.REVIEW: 4,
    NextAction.STOP: 5,
}


def allowed_actions(
    evidence_class: EvidenceClass,
    mode: DeploymentMode,
) -> frozenset[NextAction]:
    """Return the complete action set admitted by evidence and environment.

    The mode argument is explicit even though all current actions are non-writing. It
    prevents a future write action from entering this function without updating the
    total mapping and its tests.
    """

    if not isinstance(mode, DeploymentMode):
        return frozenset({NextAction.HOLD, NextAction.REVIEW, NextAction.STOP})
    if evidence_class in _EARLY_EVIDENCE:
        return frozenset({NextAction.HOLD, NextAction.REVIEW, NextAction.STOP})
    return _NON_PRODUCTION_ACTIONS


def evidence_capped_action(
    proposed_action: NextAction,
    evidence_class: EvidenceClass,
    mode: DeploymentMode,
) -> NextAction:
    """Return the proposal when allowed, otherwise fail closed to HOLD."""

    if proposed_action in allowed_actions(evidence_class, mode):
        return proposed_action
    return NextAction.HOLD


def resolve_final_action(
    proposed_action: NextAction,
    gate_results: Sequence[SignalGateResult],
) -> NextAction:
    """Combine gate coercions without consulting rationale or free-form text."""

    candidates = [proposed_action]
    for result in gate_results:
        if not result.passed:
            candidates.append(result.coerce_to or NextAction.HOLD)
    return max(candidates, key=_RESTRICTIVENESS.__getitem__)


def default_claim_wording(evidence_class: EvidenceClass) -> str:
    """Return conservative wording tied to the evidence provenance."""

    if evidence_class in _EARLY_EVIDENCE:
        return (
            "The implementation enforces the tested structural and action-ceiling "
            "invariants. It does not establish creative or revenue improvement."
        )
    if evidence_class is EvidenceClass.FROZEN_REPLAY:
        return (
            "On the named frozen replay, the system produced the recorded local "
            "artifacts. This is not a causal production result."
        )
    if evidence_class is EvidenceClass.SIMULATED:
        return (
            "Under the named simulation assumptions, the controlled signal changed "
            "the reported simulated outcome."
        )
    if evidence_class is EvidenceClass.SHADOW_ESTIMATE:
        return (
            "Under the named read-only replay assumptions, the estimated outcome is "
            "the reported value. No production write occurred."
        )
    if evidence_class is EvidenceClass.RANDOMIZED_DISPLAY_ONLY:
        return (
            "Among already-won impressions in the named authorized experiment, the "
            "variant changed the specified response by the reported amount."
        )
    if evidence_class is EvidenceClass.RANDOMIZED_END_TO_END:
        return (
            "In the named authorized traffic slice, the end-to-end treatment changed "
            "the specified causal metric with the listed guardrails."
        )
    return "The result is limited to the approved scaled-production claim register."


def build_signal_decision(
    *,
    schema_version: str,
    evidence_class: EvidenceClass,
    proposed_action: NextAction,
    mode: DeploymentMode,
    gate_results: Sequence[SignalGateResult],
    claim_wording: str | None = None,
    rationale: str = "",
) -> SignalDecision:
    """Build a decision with one authoritative IS8 result and a deterministic final action."""

    from adjacency.imagine_signal.gates import is8_evidence_action

    without_is8 = [result for result in gate_results if result.gate != "IS8"]
    is8 = is8_evidence_action(
        evidence_class=evidence_class,
        proposed_action=proposed_action,
        mode=mode,
        schema_version=schema_version,
    )
    complete = tuple(sorted((*without_is8, is8), key=lambda result: result.gate))
    gates = tuple(result.gate for result in complete)
    if len(gates) != len(set(gates)):
        raise ValueError("gate_results must contain at most one result per gate")
    final_action = resolve_final_action(proposed_action, complete)
    return SignalDecision(
        schema_version=schema_version,
        evidence_class=evidence_class,
        proposed_action=proposed_action,
        final_action=final_action,
        gate_results=complete,
        claim_wording=claim_wording or default_claim_wording(evidence_class),
        rationale=rationale,
    )
