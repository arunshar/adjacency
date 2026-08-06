"""Immutable, digest-linked decision receipt construction and verification."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from adjacency.imagine_signal.canonical import canonical_json, content_sha256
from adjacency.imagine_signal.contracts import (
    CostStatus,
    DecisionReceipt,
    HumanApproval,
    SignalDecision,
)


def _sorted_unique(values: Sequence[str], field_name: str) -> tuple[str, ...]:
    ordered = tuple(sorted(values))
    if len(ordered) != len(set(ordered)):
        raise ValueError(f"{field_name} must not contain duplicate digests")
    return ordered


def build_decision_receipt(
    *,
    schema_version: str,
    receipt_id: str,
    receipt_version: int,
    tenant_id: str,
    campaign_hash: str,
    family_hash: str,
    asset_hashes: Sequence[str],
    outcome_hashes: Sequence[str],
    scenario_hashes: Sequence[str],
    decision: SignalDecision,
    human_approval: HumanApproval | None,
    cost_total_ticks: int | None,
    cost_status: CostStatus,
    trace_id: str,
    created_at: datetime,
    previous_receipt_sha256: str | None = None,
) -> DecisionReceipt:
    """Build and sign a complete receipt from immutable source digests."""

    if human_approval is not None:
        if human_approval.receipt_id != receipt_id:
            raise ValueError("human approval is attached to another receipt")
        if human_approval.previous_receipt_sha256 != previous_receipt_sha256:
            raise ValueError("human approval does not bind the previous receipt digest")
        if human_approval.authorized_action is not decision.final_action:
            raise ValueError("human approval action does not match the final action")
    payload = {
        "schema_version": schema_version,
        "receipt_id": receipt_id,
        "receipt_version": receipt_version,
        "previous_receipt_sha256": previous_receipt_sha256,
        "tenant_id": tenant_id,
        "campaign_hash": campaign_hash,
        "family_hash": family_hash,
        "asset_hashes": _sorted_unique(asset_hashes, "asset_hashes"),
        "outcome_hashes": _sorted_unique(outcome_hashes, "outcome_hashes"),
        "scenario_hashes": _sorted_unique(scenario_hashes, "scenario_hashes"),
        "evidence_class": decision.evidence_class,
        "proposed_action": decision.proposed_action,
        "final_action": decision.final_action,
        "gate_results": decision.gate_results,
        "human_approval": human_approval,
        "claim_wording": decision.claim_wording,
        "cost_total_ticks": cost_total_ticks,
        "cost_status": cost_status,
        "trace_id": trace_id,
        "created_at": created_at,
    }
    digest = content_sha256(payload)
    return DecisionReceipt(**payload, receipt_sha256=digest)


def verify_receipt(receipt: DecisionReceipt) -> bool:
    """Recompute a receipt digest, including for unvalidated model copies."""

    unsigned = receipt.model_dump(mode="json", exclude={"receipt_sha256"})
    return content_sha256(unsigned) == receipt.receipt_sha256


def revise_receipt(
    previous: DecisionReceipt,
    *,
    decision: SignalDecision,
    approval: HumanApproval,
    created_at: datetime,
) -> DecisionReceipt:
    """Append one immutable revision linked to the exact previous receipt."""

    if approval.receipt_id != previous.receipt_id:
        raise ValueError("approval receipt_id does not match the receipt being revised")
    if approval.previous_receipt_sha256 != previous.receipt_sha256:
        raise ValueError("approval does not bind the exact previous receipt")
    return build_decision_receipt(
        schema_version=previous.schema_version,
        receipt_id=previous.receipt_id,
        receipt_version=previous.receipt_version + 1,
        previous_receipt_sha256=previous.receipt_sha256,
        tenant_id=previous.tenant_id,
        campaign_hash=previous.campaign_hash,
        family_hash=previous.family_hash,
        asset_hashes=previous.asset_hashes,
        outcome_hashes=previous.outcome_hashes,
        scenario_hashes=previous.scenario_hashes,
        decision=decision,
        human_approval=approval,
        cost_total_ticks=previous.cost_total_ticks,
        cost_status=previous.cost_status,
        trace_id=previous.trace_id,
        created_at=created_at,
    )


def receipt_json(receipt: DecisionReceipt) -> str:
    """Return canonical export JSON after verifying its digest."""

    if not verify_receipt(receipt):
        raise ValueError("cannot export a receipt with an invalid digest")
    return canonical_json(receipt)
