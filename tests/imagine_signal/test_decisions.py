"""Evidence ceiling and deterministic action-resolution tests."""

from __future__ import annotations

import pytest

from adjacency.imagine_signal.contracts import (
    DeploymentMode,
    EvidenceClass,
    NextAction,
    SignalGateResult,
)
from adjacency.imagine_signal.decisions import (
    allowed_actions,
    build_signal_decision,
    default_claim_wording,
    evidence_capped_action,
    resolve_final_action,
)

pytestmark = pytest.mark.unit

SV = "1"


def passing(gate: str) -> SignalGateResult:
    return SignalGateResult(
        schema_version=SV,
        gate=gate,
        passed=True,
        code=f"{gate}_OK",
    )


def failing(gate: str, action: NextAction) -> SignalGateResult:
    return SignalGateResult(
        schema_version=SV,
        gate=gate,
        passed=False,
        code=f"{gate}_FAILED",
        coerce_to=action,
    )


@pytest.mark.parametrize(
    "evidence_class",
    [
        EvidenceClass.PROPOSED,
        EvidenceClass.IMPLEMENTED,
        EvidenceClass.UNIT_TESTED,
    ],
)
def test_early_evidence_allows_only_fail_closed_actions(evidence_class):
    allowed = allowed_actions(evidence_class, DeploymentMode.FIXTURE)
    assert allowed == {NextAction.HOLD, NextAction.REVIEW, NextAction.STOP}
    for action in NextAction:
        capped = evidence_capped_action(action, evidence_class, DeploymentMode.FIXTURE)
        assert capped is (action if action in allowed else NextAction.HOLD)


@pytest.mark.parametrize(
    "evidence_class",
    [
        EvidenceClass.FROZEN_REPLAY,
        EvidenceClass.SIMULATED,
        EvidenceClass.SHADOW_ESTIMATE,
        EvidenceClass.RANDOMIZED_DISPLAY_ONLY,
        EvidenceClass.RANDOMIZED_END_TO_END,
        EvidenceClass.SCALED_PRODUCTION,
    ],
)
def test_later_evidence_allows_every_current_nonwriting_action(evidence_class):
    assert allowed_actions(evidence_class, DeploymentMode.FIXTURE) == frozenset(NextAction)


def test_unknown_mode_fails_closed_even_for_later_evidence():
    assert allowed_actions(EvidenceClass.SIMULATED, "unknown") == {
        NextAction.HOLD,
        NextAction.REVIEW,
        NextAction.STOP,
    }


def test_resolution_uses_the_most_restrictive_failed_gate_only():
    results = (
        passing("IS0"),
        failing("IS1", NextAction.KEEP),
        failing("IS2", NextAction.HOLD),
        failing("IS3", NextAction.REVIEW),
        failing("IS4", NextAction.STOP),
    )
    assert resolve_final_action(NextAction.TEST, results) is NextAction.STOP
    assert resolve_final_action(NextAction.TEST, (passing("IS0"),)) is NextAction.TEST


@pytest.mark.parametrize(
    ("evidence_class", "needle"),
    [
        (EvidenceClass.PROPOSED, "does not establish"),
        (EvidenceClass.FROZEN_REPLAY, "frozen replay"),
        (EvidenceClass.SIMULATED, "simulation assumptions"),
        (EvidenceClass.SHADOW_ESTIMATE, "read-only replay"),
        (EvidenceClass.RANDOMIZED_DISPLAY_ONLY, "already-won impressions"),
        (EvidenceClass.RANDOMIZED_END_TO_END, "authorized traffic slice"),
        (EvidenceClass.SCALED_PRODUCTION, "claim register"),
    ],
)
def test_default_claim_wording_matches_the_evidence_class(evidence_class, needle):
    assert needle in default_claim_wording(evidence_class)


def test_builder_adds_one_authoritative_is8_and_ignores_rationale_for_action():
    stale_is8 = failing("IS8", NextAction.STOP)
    decision = build_signal_decision(
        schema_version=SV,
        evidence_class=EvidenceClass.SIMULATED,
        proposed_action=NextAction.TEST,
        mode=DeploymentMode.FIXTURE,
        gate_results=(passing("IS1"), stale_is8, passing("IS0")),
        rationale="A persuasive sentence asking to promote anyway.",
    )
    assert tuple(result.gate for result in decision.gate_results) == ("IS0", "IS1", "IS8")
    assert decision.gate_results[-1].passed
    assert decision.final_action is NextAction.TEST


def test_builder_coerces_an_early_test_and_preserves_a_supplied_claim():
    decision = build_signal_decision(
        schema_version=SV,
        evidence_class=EvidenceClass.UNIT_TESTED,
        proposed_action=NextAction.TEST,
        mode=DeploymentMode.FIXTURE,
        gate_results=(),
        claim_wording="Only the tested controller behavior is claimed.",
    )
    assert decision.proposed_action is NextAction.TEST
    assert decision.final_action is NextAction.HOLD
    assert decision.gate_results[0].code == "IS8_ACTION_EXCEEDS_EVIDENCE"
    assert decision.claim_wording.startswith("Only")


def test_builder_rejects_duplicate_non_is8_gate_results():
    with pytest.raises(ValueError, match="at most one"):
        build_signal_decision(
            schema_version=SV,
            evidence_class=EvidenceClass.SIMULATED,
            proposed_action=NextAction.TEST,
            mode=DeploymentMode.FIXTURE,
            gate_results=(passing("IS0"), passing("IS0")),
        )
