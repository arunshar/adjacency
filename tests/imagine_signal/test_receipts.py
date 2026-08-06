"""Digest-linked receipt construction, tamper, and revision tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from adjacency.imagine_signal.canonical import content_sha256
from adjacency.imagine_signal.contracts import (
    CostStatus,
    EvidenceClass,
    HumanApproval,
    NextAction,
    SignalDecision,
    SignalGateResult,
)
from adjacency.imagine_signal.receipts import (
    build_decision_receipt,
    receipt_json,
    revise_receipt,
    verify_receipt,
)

pytestmark = pytest.mark.unit

SV = "1"
H0 = "0" * 64
H1 = "1" * 64
H2 = "2" * 64
CREATED = datetime(2026, 8, 5, tzinfo=UTC)


def make_gate(
    *,
    passed: bool = True,
    action: NextAction | None = None,
) -> SignalGateResult:
    return SignalGateResult(
        schema_version=SV,
        gate="IS8",
        passed=passed,
        code="IS8_OK" if passed else "IS8_ACTION_EXCEEDS_EVIDENCE",
        coerce_to=action,
    )


def make_decision(
    *,
    proposed: NextAction = NextAction.TEST,
    final: NextAction = NextAction.TEST,
    gate: SignalGateResult | None = None,
) -> SignalDecision:
    return SignalDecision(
        schema_version=SV,
        evidence_class=EvidenceClass.SIMULATED,
        proposed_action=proposed,
        final_action=final,
        gate_results=(gate or make_gate(),),
        claim_wording="Under the named simulation, the reported result is simulated.",
        rationale="display only",
    )


def make_receipt(**updates):
    values = {
        "schema_version": SV,
        "receipt_id": "receipt",
        "receipt_version": 1,
        "tenant_id": "tenant",
        "campaign_hash": H0,
        "family_hash": H1,
        "asset_hashes": (H1, H0),
        "outcome_hashes": (H2,),
        "scenario_hashes": (H0,),
        "decision": make_decision(),
        "human_approval": None,
        "cost_total_ticks": 10,
        "cost_status": CostStatus.EXACT,
        "trace_id": "trace",
        "created_at": CREATED,
        "previous_receipt_sha256": None,
    }
    values.update(updates)
    return build_decision_receipt(**values)


def make_approval(previous, **updates) -> HumanApproval:
    values = {
        "schema_version": SV,
        "approval_id": "approval",
        "receipt_id": previous.receipt_id,
        "previous_receipt_sha256": previous.receipt_sha256,
        "actor_id": "reviewer",
        "authorized_action": NextAction.TEST,
        "reason_code": "APPROVED_TEST",
        "comment": "reviewed",
        "approved_at": CREATED + timedelta(minutes=1),
    }
    values.update(updates)
    return HumanApproval(**values)


def rebuild_receipt(receipt, **updates):
    payload = receipt.model_dump(mode="python", exclude={"receipt_sha256"})
    payload.update(updates)
    payload["receipt_sha256"] = content_sha256(payload)
    return type(receipt)(**payload)


def test_builder_sorts_source_hashes_and_produces_a_verifiable_export():
    receipt = make_receipt()
    assert receipt.asset_hashes == (H0, H1)
    assert receipt.content_hash == receipt.receipt_sha256
    assert verify_receipt(receipt)
    exported = receipt_json(receipt)
    assert f'"receipt_sha256":"{receipt.receipt_sha256}"' in exported


@pytest.mark.parametrize(
    ("field", "values"),
    [
        ("asset_hashes", (H0, H0)),
        ("outcome_hashes", (H1, H1)),
        ("scenario_hashes", (H2, H2)),
    ],
)
def test_builder_rejects_duplicate_source_digests(field, values):
    with pytest.raises(ValueError, match="must not contain duplicate"):
        make_receipt(**{field: values})


def test_builder_rejects_approval_bound_to_another_receipt_digest_or_action():
    previous = make_receipt()
    with pytest.raises(ValueError, match="another receipt"):
        make_receipt(
            receipt_version=2,
            previous_receipt_sha256=previous.receipt_sha256,
            human_approval=make_approval(previous, receipt_id="other"),
        )
    with pytest.raises(ValueError, match="previous receipt digest"):
        make_receipt(
            receipt_version=2,
            previous_receipt_sha256=previous.receipt_sha256,
            human_approval=make_approval(previous, previous_receipt_sha256=H2),
        )
    with pytest.raises(ValueError, match="does not match the final action"):
        make_receipt(
            receipt_version=2,
            previous_receipt_sha256=previous.receipt_sha256,
            human_approval=make_approval(previous, authorized_action=NextAction.STOP),
        )


def test_receipt_contract_rejects_bad_revision_links_costs_and_time():
    receipt = make_receipt()
    with pytest.raises(ValidationError, match="version 1"):
        rebuild_receipt(receipt, previous_receipt_sha256=H2)
    with pytest.raises(ValidationError, match="must link"):
        rebuild_receipt(receipt, receipt_version=2)
    with pytest.raises(ValidationError, match="unknown total cost"):
        rebuild_receipt(receipt, cost_status=CostStatus.UNKNOWN)
    with pytest.raises(ValidationError, match="requires a value"):
        rebuild_receipt(receipt, cost_total_ticks=None)
    with pytest.raises(ValidationError, match="must include"):
        rebuild_receipt(receipt, created_at=CREATED.replace(tzinfo=None))


@pytest.mark.parametrize("field", ["asset_hashes", "outcome_hashes", "scenario_hashes"])
def test_receipt_contract_rejects_malformed_source_hashes(field):
    receipt = make_receipt()
    with pytest.raises(ValidationError, match="must contain SHA-256"):
        rebuild_receipt(receipt, **{field: ("not-a-hash",)})


def test_tampering_is_detected_even_when_model_copy_skips_validation():
    receipt = make_receipt()
    tampered = receipt.model_copy(update={"claim_wording": "This proves revenue lift."})
    assert not verify_receipt(tampered)
    with pytest.raises(ValueError, match="invalid digest"):
        receipt_json(tampered)


def test_direct_construction_rejects_a_wrong_receipt_digest():
    receipt = make_receipt()
    payload = receipt.model_dump(mode="python")
    payload["receipt_sha256"] = H2
    with pytest.raises(ValidationError, match="does not match"):
        type(receipt)(**payload)


def test_revision_is_append_only_and_binds_human_approval():
    previous = make_receipt()
    approval = make_approval(previous)
    revised = revise_receipt(
        previous,
        decision=make_decision(),
        approval=approval,
        created_at=CREATED + timedelta(minutes=2),
    )
    assert previous.receipt_version == 1
    assert revised.receipt_version == 2
    assert revised.previous_receipt_sha256 == previous.receipt_sha256
    assert revised.human_approval == approval
    assert revised.receipt_sha256 != previous.receipt_sha256
    assert verify_receipt(revised)


def test_receipt_contract_rechecks_embedded_approval_binding():
    previous = make_receipt()
    approval = make_approval(previous)
    revised = revise_receipt(
        previous,
        decision=make_decision(),
        approval=approval,
        created_at=CREATED + timedelta(minutes=2),
    )
    invalid_cases = (
        (approval.model_copy(update={"receipt_id": "other"}), "another receipt"),
        (
            approval.model_copy(update={"previous_receipt_sha256": H2}),
            "does not bind",
        ),
        (
            approval.model_copy(update={"authorized_action": NextAction.STOP}),
            "does not match final_action",
        ),
    )
    for invalid, message in invalid_cases:
        with pytest.raises(ValidationError, match=message):
            rebuild_receipt(revised, human_approval=invalid)


def test_revision_rejects_approval_for_another_receipt_or_digest():
    previous = make_receipt()
    with pytest.raises(ValueError, match="receipt_id"):
        revise_receipt(
            previous,
            decision=make_decision(),
            approval=make_approval(previous, receipt_id="other"),
            created_at=CREATED,
        )
    with pytest.raises(ValueError, match="exact previous"):
        revise_receipt(
            previous,
            decision=make_decision(),
            approval=make_approval(previous, previous_receipt_sha256=H2),
            created_at=CREATED,
        )
