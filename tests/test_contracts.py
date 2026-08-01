"""Tests for the four frozen contracts.

The contracts are where a malformed object gets rejected before any gate has to reason
about it. A validator that does not fire is a validator that is not there.
"""

from __future__ import annotations

import pytest
from conftest import PROSE, clause_from_prose

from adjacency.contracts import (
    SEVERITY_ACTION,
    Action,
    Clause,
    DeltaKind,
    DeltaRow,
    ImageEvidence,
    InventoryItem,
    Media,
    PolicySpec,
    TextEvidence,
    Verdict,
    normalize,
)
from adjacency.gates import GateResult

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------------------
# Clause
# --------------------------------------------------------------------------------------


def test_clause_rejects_an_inverted_span():
    with pytest.raises(ValueError, match="must exceed"):
        Clause(
            clause_id="C1",
            category="safety",
            severity=1,
            description="d",
            source_text="abc",
            source_start=10,
            source_end=5,
        )


def test_clause_rejects_a_span_whose_width_disagrees_with_its_text():
    # Catches the off-by-one that would otherwise surface as a confusing G0 failure.
    with pytest.raises(ValueError, match="does not match source_text length"):
        Clause(
            clause_id="C1",
            category="safety",
            severity=1,
            description="d",
            source_text="abc",
            source_start=0,
            source_end=99,
        )


@pytest.mark.parametrize("severity", [-1, 5])
def test_clause_rejects_severity_outside_the_table(severity):
    with pytest.raises(ValueError):
        Clause(
            clause_id="C1",
            category="safety",
            severity=severity,
            description="d",
            source_text="abc",
            source_start=0,
            source_end=3,
        )


# --------------------------------------------------------------------------------------
# PolicySpec
# --------------------------------------------------------------------------------------


def test_policyspec_rejects_duplicate_clause_ids():
    c = clause_from_prose("C1", "content celebrating violence", severity=3)
    with pytest.raises(ValueError, match="duplicate clause_id"):
        PolicySpec(version=1, advertiser="X", prose=PROSE, clauses=(c, c))


def test_policy_hash_is_stable_across_identical_construction(spec):
    twin = PolicySpec(
        version=spec.version,
        advertiser=spec.advertiser,
        prose=spec.prose,
        clauses=spec.clauses,
    )
    assert spec.policy_hash == twin.policy_hash


def test_policy_hash_changes_when_any_clause_changes(spec):
    altered = spec.model_copy(
        update={
            "clauses": (
                spec.clauses[0].model_copy(update={"severity": 2}),
                spec.clauses[1],
            )
        }
    )
    assert altered.policy_hash != spec.policy_hash


def test_policy_hash_changes_with_the_version(spec):
    # A revision must not hash the same as what it replaced, or the ledger cannot tell
    # two runs apart.
    assert spec.model_copy(update={"version": 2}).policy_hash != spec.policy_hash


def test_clause_lookup_returns_none_for_an_unknown_id(spec):
    assert spec.clause("C1") is not None
    assert spec.clause("nope") is None


def test_clause_ids_exposes_the_whole_set(spec):
    assert spec.clause_ids == frozenset({"C1", "C2"})


def test_prose_is_nfc_normalized_on_construction():
    # Decomposed e-acute becomes composed, so offsets computed later mean one thing.
    decomposed = "café content"
    spec = PolicySpec(
        version=1,
        advertiser="X",
        prose=decomposed,
        clauses=(
            Clause(
                clause_id="C1",
                category="c",
                severity=1,
                description="d",
                source_text="café",
                source_start=0,
                source_end=4,
            ),
        ),
    )
    assert spec.prose == normalize(decomposed)
    assert len(spec.prose) == len("café content")


# --------------------------------------------------------------------------------------
# InventoryItem
# --------------------------------------------------------------------------------------


def test_item_text_is_normalized():
    item = InventoryItem(item_id="i", text="café")
    assert item.text == "café"


def test_has_media_reflects_attachments(item, clean_item):
    assert item.has_media
    assert not clean_item.has_media


def test_media_lookup_returns_none_for_an_unknown_id(item):
    assert item.media_by_id("m1") is not None
    assert item.media_by_id("nope") is None


def test_media_rejects_a_non_positive_dimension():
    with pytest.raises(ValueError):
        Media(media_id="m", kind="image", width=0, height=10)


def test_item_defaults_to_empty_text_and_no_media():
    bare = InventoryItem(item_id="i")
    assert bare.text == ""
    assert bare.media == ()
    assert not bare.has_media


# --------------------------------------------------------------------------------------
# Verdict
# --------------------------------------------------------------------------------------


def test_contracts_are_frozen(item):
    with pytest.raises(ValueError):
        item.item_id = "mutated"


def test_contracts_reject_undeclared_fields():
    with pytest.raises(ValueError):
        InventoryItem(item_id="i", nonsense="x")


def test_coerced_to_returns_a_copy_and_annotates_the_rationale():
    v = Verdict(
        item_id="i",
        action=Action.ALLOW,
        severity=0,
        confidence=0.9,
        rationale="looked fine",
        policy_version=1,
    )
    coerced = v.coerced_to(Action.REVIEW, reason="G1_SPAN_NOT_FOUND")
    assert v.action is Action.ALLOW
    assert coerced.action is Action.REVIEW
    assert "looked fine" in coerced.rationale
    assert "G1_SPAN_NOT_FOUND" in coerced.rationale


def test_coerced_to_works_on_an_empty_rationale():
    v = Verdict(item_id="i", action=Action.ALLOW, severity=0, confidence=0.9, policy_version=1)
    assert v.coerced_to(Action.BLOCK, reason="G5").rationale.startswith("[coerced")


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_verdict_rejects_confidence_outside_zero_to_one(confidence):
    with pytest.raises(ValueError):
        Verdict(
            item_id="i",
            action=Action.ALLOW,
            severity=0,
            confidence=confidence,
            policy_version=1,
        )


def test_evidence_types_carry_their_discriminator():
    assert TextEvidence(quote="q", start=0, end=1).kind == "text"
    assert ImageEvidence(media_id="m", x=0, y=0, w=1, h=1).kind == "image"


# --------------------------------------------------------------------------------------
# DeltaRow
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("engine", "baseline", "expected"),
    [
        (Action.BLOCK, Action.BLOCK, DeltaKind.AGREE),
        (Action.ALLOW, Action.ALLOW, DeltaKind.AGREE),
        (Action.REVIEW, Action.ALLOW, DeltaKind.AGREE),
        (Action.ALLOW, Action.BLOCK, DeltaKind.OVER_BLOCK),
        (Action.BLOCK, Action.ALLOW, DeltaKind.UNDER_BLOCK),
        (Action.BLOCK, Action.REVIEW, DeltaKind.UNDER_BLOCK),
    ],
)
def test_delta_kind_classification(engine, baseline, expected):
    row = DeltaRow(item_id="i", engine_action=engine, baseline_action=baseline)
    assert row.kind is expected


def test_delta_row_carries_the_terms_that_fired():
    row = DeltaRow(
        item_id="i",
        engine_action=Action.ALLOW,
        baseline_action=Action.BLOCK,
        matched_terms=("crash", "accident"),
    )
    assert row.kind is DeltaKind.OVER_BLOCK
    assert row.matched_terms == ("crash", "accident")


# --------------------------------------------------------------------------------------
# The severity table itself
# --------------------------------------------------------------------------------------


def test_severity_table_covers_every_legal_severity():
    assert set(SEVERITY_ACTION) == {0, 1, 2, 3, 4}


def test_severity_table_is_monotonic():
    # Severity must never map to a laxer action as it increases, or G4 would license
    # exactly the incoherence it exists to catch.
    rank = {Action.ALLOW: 0, Action.REVIEW: 1, Action.BLOCK: 2}
    ranks = [rank[SEVERITY_ACTION[s]] for s in sorted(SEVERITY_ACTION)]
    assert ranks == sorted(ranks)


# --------------------------------------------------------------------------------------
# GateResult ergonomics
# --------------------------------------------------------------------------------------


def test_gate_result_is_truthy_when_it_passed():
    assert bool(GateResult(gate="G1", passed=True))
    assert not bool(GateResult(gate="G1", passed=False, code="X"))
