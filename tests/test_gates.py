"""Exhaustive tests for the seven gates.

Every failure branch of every gate has a test. These are pure functions with no excuse
for an uncovered branch, and they are the modules a reviewer will actually read.
"""

from __future__ import annotations

import pytest
from conftest import PROSE, make_verdict, text_evidence_for

from adjacency.contracts import (
    Action,
    Clause,
    ImageEvidence,
    InventoryItem,
    PolicySpec,
    TextEvidence,
)
from adjacency.gates import (
    Budget,
    g0_source_spans,
    g1_evidence_grounding,
    g2_clause_existence,
    g3_monotonicity,
    g4_severity_coherence,
    g5_budget,
    g6_abstention_floor,
    run_verdict_gates,
)

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------------------
# G0
# --------------------------------------------------------------------------------------


def test_g0_passes_when_every_span_reproduces_its_source_text(spec):
    assert all(r.passed for r in g0_source_spans(spec))


def test_g0_catches_a_span_that_points_at_different_text():
    # A clause claiming text that is not at the offsets it gives. This is what an
    # invented rule looks like: plausible prose, wrong provenance.
    bad = Clause(
        clause_id="C9",
        category="safety",
        severity=3,
        description="invented",
        source_text="celebrating violence",
        source_start=0,
        source_end=20,
    )
    spec = PolicySpec(version=1, advertiser="X", prose=PROSE, clauses=(bad,))
    results = g0_source_spans(spec)
    assert not results[0].passed
    assert results[0].code == "G0_SPAN_MISMATCH"


def test_g0_catches_a_span_running_past_the_end_of_the_prose():
    prose = "Short policy."
    filler = "y" * 200
    bad = Clause(
        clause_id="C9",
        category="safety",
        severity=1,
        description="runs past the end",
        source_text=filler,
        source_start=5,
        source_end=205,
    )
    spec = PolicySpec(version=1, advertiser="X", prose=prose, clauses=(bad,))
    results = g0_source_spans(spec)
    assert not results[0].passed
    assert results[0].code == "G0_SPAN_OUT_OF_RANGE"


# --------------------------------------------------------------------------------------
# G1: the hallucination gate
# --------------------------------------------------------------------------------------


def test_g1_passes_on_evidence_that_is_actually_there(item):
    ev = text_evidence_for(item, "aviation accident")
    assert g1_evidence_grounding(make_verdict(evidence=(ev,)), item).passed


def test_g1_catches_a_quote_that_is_not_in_the_post(item):
    # The model cites a plausible phrase that does not appear. This is the gate that
    # fires on stage.
    ev = TextEvidence(quote="a burning fuselage", start=10, end=28)
    result = g1_evidence_grounding(make_verdict(evidence=(ev,)), item)
    assert not result.passed
    assert result.code == "G1_SPAN_NOT_FOUND"
    assert result.coerce_to is Action.REVIEW


def test_g1_catches_a_span_past_the_end_of_the_text(item):
    ev = TextEvidence(quote="anything", start=5000, end=5008)
    result = g1_evidence_grounding(make_verdict(evidence=(ev,)), item)
    assert not result.passed
    assert result.code == "G1_SPAN_OUT_OF_RANGE"


def test_g1_catches_an_inverted_span(item):
    ev = TextEvidence(quote="x", start=10, end=10)
    result = g1_evidence_grounding(make_verdict(evidence=(ev,)), item)
    assert not result.passed
    assert result.code == "G1_SPAN_MALFORMED"


def test_g1_catches_evidence_about_media_that_is_not_attached(item):
    ev = ImageEvidence(media_id="does-not-exist", x=0, y=0, w=10, h=10)
    result = g1_evidence_grounding(make_verdict(evidence=(ev,)), item)
    assert not result.passed
    assert result.code == "G1_MEDIA_NOT_FOUND"


@pytest.mark.parametrize(
    ("x", "y", "w", "h"),
    [
        (1190, 0, 20, 10),  # runs off the right edge
        (0, 795, 10, 20),  # runs off the bottom edge
        (0, 0, 1201, 10),  # wider than the frame
    ],
)
def test_g1_catches_a_box_outside_the_frame(item, x, y, w, h):
    ev = ImageEvidence(media_id="m1", x=x, y=y, w=w, h=h)
    result = g1_evidence_grounding(make_verdict(evidence=(ev,)), item)
    assert not result.passed
    assert result.code == "G1_BBOX_OUT_OF_BOUNDS"


def test_g1_accepts_a_box_flush_against_the_frame_edge(item):
    # Exactly filling the frame is legal. Off-by-one here would reject valid evidence.
    ev = ImageEvidence(media_id="m1", x=0, y=0, w=1200, h=800)
    assert g1_evidence_grounding(make_verdict(evidence=(ev,)), item).passed


def test_g1_indexes_by_character_not_byte_so_emoji_do_not_break_spans():
    """The offsets are character offsets, and this proves it matters.

    A post with a ZWJ emoji sequence has a different length in characters, bytes, and
    UTF-16 code units. If the gate indexed bytes while the contract stored characters,
    every post containing an emoji before the citation would fail spuriously, and X
    posts are full of emoji.
    """
    # man + ZWJ + woman + ZWJ + girl + ZWJ + boy: one grapheme, seven code points.
    family = "\U0001f468‍\U0001f469‍\U0001f467‍\U0001f466"
    assert len(family) == 7
    text = f"Family {family} plane crash today"
    item = InventoryItem(item_id="e1", text=text)
    needle = "plane crash"

    char_start = item.text.index(needle)
    byte_start = len(item.text[:char_start].encode("utf-8"))
    # The two disagree, which is the whole point of the test.
    assert byte_start != char_start

    good = TextEvidence(quote=needle, start=char_start, end=char_start + len(needle))
    assert g1_evidence_grounding(make_verdict(evidence=(good,)), item).passed

    # A model that reported a byte offset gets caught rather than silently trusted.
    bad = TextEvidence(quote=needle, start=byte_start, end=byte_start + len(needle))
    assert g1_evidence_grounding(make_verdict(evidence=(bad,)), item).code == (
        "G1_SPAN_OUT_OF_RANGE"
    )


def test_g1_passes_when_there_is_no_evidence_at_all(clean_item):
    # Tier-0 decisions carry no evidence. G1 has nothing to check and must not invent
    # a failure; the abstention floor is what guards low-information verdicts.
    assert g1_evidence_grounding(make_verdict(item_id="post-2"), clean_item).passed


# --------------------------------------------------------------------------------------
# G2
# --------------------------------------------------------------------------------------


def test_g2_passes_on_a_clause_that_exists(spec):
    assert g2_clause_existence(make_verdict(clause_ids=("C1",)), spec).passed


def test_g2_catches_an_invented_clause_id(spec):
    result = g2_clause_existence(make_verdict(clause_ids=("C1", "C99")), spec)
    assert not result.passed
    assert result.code == "G2_CLAUSE_NOT_FOUND"
    assert "C99" in result.detail


def test_g2_catches_a_verdict_judged_against_a_different_policy_version(spec):
    result = g2_clause_existence(make_verdict(policy_version=2), spec)
    assert not result.passed
    assert result.code == "G2_VERSION_MISMATCH"


# --------------------------------------------------------------------------------------
# G3: the reward-hacking gate
# --------------------------------------------------------------------------------------


def test_g3_allows_a_revision_that_only_tightens():
    report = g3_monotonicity(
        previous={"a": Action.ALLOW, "b": Action.ALLOW},
        proposed={"a": Action.BLOCK, "b": Action.ALLOW},
    )
    assert report.result.passed
    assert report.flipped_to_allow == ()


def test_g3_blocks_a_revision_that_loosens_without_approval():
    report = g3_monotonicity(
        previous={"a": Action.BLOCK, "b": Action.BLOCK},
        proposed={"a": Action.ALLOW, "b": Action.ALLOW},
    )
    assert not report.result.passed
    assert report.result.code == "G3_UNAPPROVED_LOOSENING"
    assert report.flipped_to_allow == ("a", "b")


def test_g3_permits_a_loosening_that_a_human_signed_off_on():
    report = g3_monotonicity(
        previous={"a": Action.BLOCK},
        proposed={"a": Action.ALLOW},
        approvals=frozenset({"a"}),
    )
    assert report.result.passed
    assert report.approved == ("a",)
    assert report.flipped_to_allow == ()


def test_g3_ignores_items_absent_from_the_proposed_run():
    # A holdout item the new policy did not score cannot have been loosened by it.
    report = g3_monotonicity(previous={"a": Action.BLOCK}, proposed={})
    assert report.result.passed


def test_g3_does_not_treat_block_to_review_as_loosening():
    # REVIEW does not serve an ad, so BLOCK to REVIEW is not a loosening.
    report = g3_monotonicity(previous={"a": Action.BLOCK}, proposed={"a": Action.REVIEW})
    assert report.result.passed


# --------------------------------------------------------------------------------------
# G4
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("severity", "action"),
    [
        (0, Action.ALLOW),
        (1, Action.ALLOW),
        (2, Action.REVIEW),
        (3, Action.BLOCK),
        (4, Action.BLOCK),
    ],
)
def test_g4_passes_on_every_coherent_severity_action_pair(severity, action):
    assert g4_severity_coherence(make_verdict(severity=severity, action=action)).passed


def test_g4_catches_the_dangerous_incoherence(spec):
    # severity 4 with action ALLOW is the combination that actually costs money.
    result = g4_severity_coherence(make_verdict(severity=4, action=Action.ALLOW))
    assert not result.passed
    assert result.code == "G4_SEVERITY_INCOHERENT"
    assert result.coerce_to is Action.BLOCK


def test_g4_coerces_to_review_rather_than_allow_when_the_table_says_allow():
    # If the table says ALLOW but the model said BLOCK, we do not auto-loosen to ALLOW.
    # The disagreement itself is a reason for a human to look.
    result = g4_severity_coherence(make_verdict(severity=0, action=Action.BLOCK))
    assert not result.passed
    assert result.coerce_to is Action.REVIEW


# --------------------------------------------------------------------------------------
# G5
# --------------------------------------------------------------------------------------


def test_g5_passes_inside_every_cap():
    b = Budget(max_tokens=1000, max_tool_calls=10, max_wallclock_s=60.0)
    b.charge(tokens=500, tool_calls=5, seconds=30.0)
    assert g5_budget(b).passed


@pytest.mark.parametrize(
    ("kwargs", "needle"),
    [
        ({"tokens": 1001}, "tokens"),
        ({"tool_calls": 11}, "tool calls"),
        ({"seconds": 61.0}, "elapsed"),
    ],
)
def test_g5_catches_each_kind_of_breach(kwargs, needle):
    b = Budget(max_tokens=1000, max_tool_calls=10, max_wallclock_s=60.0)
    b.charge(**kwargs)
    result = g5_budget(b)
    assert not result.passed
    assert result.code == "G5_BUDGET_EXCEEDED"
    assert needle in result.detail
    # Fail closed toward BLOCK: the advertiser loses reach, never safety.
    assert result.coerce_to is Action.BLOCK


def test_g5_reports_every_simultaneous_breach():
    b = Budget(max_tokens=10, max_tool_calls=1, max_wallclock_s=1.0)
    b.charge(tokens=100, tool_calls=5, seconds=10.0)
    detail = g5_budget(b).detail
    assert "tokens" in detail and "tool calls" in detail and "elapsed" in detail


def test_g5_treats_exactly_at_the_cap_as_within_budget():
    b = Budget(max_tokens=100, max_tool_calls=1, max_wallclock_s=1.0)
    b.charge(tokens=100, tool_calls=1, seconds=1.0)
    assert g5_budget(b).passed


# --------------------------------------------------------------------------------------
# G6
# --------------------------------------------------------------------------------------


def test_g6_passes_a_confident_allow():
    assert g6_abstention_floor(
        make_verdict(action=Action.ALLOW, severity=0, confidence=0.95)
    ).passed


def test_g6_catches_a_low_confidence_allow():
    result = g6_abstention_floor(make_verdict(action=Action.ALLOW, severity=0, confidence=0.3))
    assert not result.passed
    assert result.code == "G6_BELOW_CONFIDENCE_FLOOR"
    assert result.coerce_to is Action.REVIEW


def test_g6_does_not_second_guess_a_low_confidence_block():
    # The floor is asymmetric on purpose. An uncertain BLOCK is already the safe side.
    assert g6_abstention_floor(make_verdict(action=Action.BLOCK, severity=3, confidence=0.1)).passed


def test_g6_catches_the_two_effort_levels_disagreeing():
    low = make_verdict(action=Action.ALLOW, severity=0, confidence=0.9)
    high = make_verdict(action=Action.BLOCK, severity=3, confidence=0.9)
    result = g6_abstention_floor(low, escalated=high)
    assert not result.passed
    assert result.code == "G6_EFFORT_DISAGREEMENT"
    assert result.coerce_to is Action.REVIEW


def test_g6_ignores_disagreement_that_does_not_involve_allow():
    # BLOCK versus REVIEW is a disagreement about how to not serve. Nothing is at risk.
    low = make_verdict(action=Action.BLOCK, severity=3)
    high = make_verdict(action=Action.REVIEW, severity=2)
    assert g6_abstention_floor(low, escalated=high).passed


# --------------------------------------------------------------------------------------
# The chain
# --------------------------------------------------------------------------------------


def test_chain_passes_a_well_formed_verdict(item, spec):
    ev = text_evidence_for(item, "aviation accident")
    v = make_verdict(action=Action.BLOCK, severity=3, clause_ids=("C1",), evidence=(ev,))
    chained = run_verdict_gates(v, item, spec)
    assert chained.passed
    assert chained.verdict.action is Action.BLOCK
    assert chained.codes == ()


def test_chain_flips_a_hallucinated_allow_to_review(item, spec):
    """The demo beat: a confident ALLOW citing evidence that is not there."""
    ev = TextEvidence(quote="a burning fuselage", start=0, end=18)
    v = make_verdict(
        action=Action.ALLOW, severity=0, clause_ids=("C1",), evidence=(ev,), confidence=0.98
    )
    chained = run_verdict_gates(v, item, spec)
    assert not chained.passed
    assert "G1_SPAN_NOT_FOUND" in chained.codes
    assert chained.verdict.action is Action.REVIEW
    assert "coerced to REVIEW" in chained.verdict.rationale


def test_chain_applies_the_strictest_coercion_when_gates_disagree(item, spec):
    # G4 wants BLOCK (severity 4 with ALLOW), G6 wants REVIEW (low confidence ALLOW).
    # BLOCK is stricter, so BLOCK wins regardless of the order the gates ran in.
    v = make_verdict(action=Action.ALLOW, severity=4, clause_ids=("C1",), confidence=0.2)
    chained = run_verdict_gates(v, item, spec)
    assert chained.verdict.action is Action.BLOCK
    assert {"G4_SEVERITY_INCOHERENT", "G6_BELOW_CONFIDENCE_FLOOR"} <= set(chained.codes)


def test_chain_records_every_failure_not_just_the_first(item, spec):
    v = make_verdict(
        action=Action.ALLOW,
        severity=4,
        clause_ids=("C99",),
        evidence=(TextEvidence(quote="nope", start=0, end=4),),
        confidence=0.1,
        policy_version=1,
    )
    chained = run_verdict_gates(v, item, spec)
    # G1, G2, G4 and G6 all have something to say about this verdict.
    assert len(chained.failures) == 4


def test_chain_leaves_the_original_verdict_intact_in_the_result(item, spec):
    # Coercion returns a copy. The ledger needs the model's original claim next to the
    # override, otherwise you cannot audit what the model actually said.
    ev = TextEvidence(quote="not present", start=0, end=11)
    original = make_verdict(action=Action.ALLOW, severity=0, evidence=(ev,), clause_ids=("C1",))
    chained = run_verdict_gates(original, item, spec)
    assert original.action is Action.ALLOW
    assert chained.verdict.action is Action.REVIEW
    assert chained.verdict is not original
