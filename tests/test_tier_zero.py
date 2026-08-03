from __future__ import annotations

from adjacency.contracts import Action, InventoryItem, Media
from adjacency.tier_zero import TierZeroCode, decide_tier_zero


def test_clean_text_is_allowed_without_model_cost():
    result = decide_tier_zero(
        InventoryItem(item_id="clean", text="A routine weather update."),
        policy_version=3,
    )

    assert result.decided
    assert result.code is TierZeroCode.CLEAN_TEXT_ALLOW
    assert result.verdict is not None
    assert result.verdict.action is Action.ALLOW
    assert result.verdict.severity == 0
    assert result.verdict.confidence == 1.0
    assert result.verdict.tier == 0
    assert result.verdict.policy_version == 3
    assert result.verdict.clause_ids == ()
    assert result.verdict.evidence == ()


def test_media_empty_text_term_matches_and_carve_outs_escalate():
    media_item = InventoryItem(
        item_id="media",
        text="Clean caption",
        media=(Media(media_id="image", kind="image", width=10, height=10),),
    )
    cases = [
        (
            decide_tier_zero(media_item, policy_version=1),
            TierZeroCode.MEDIA_REQUIRES_MODEL,
        ),
        (
            decide_tier_zero(InventoryItem(item_id="empty"), policy_version=1),
            TierZeroCode.EMPTY_TEXT_REQUIRES_REVIEW,
        ),
        (
            decide_tier_zero(
                InventoryItem(item_id="match", text="A risky term"),
                policy_version=1,
                matched_terms=("risky",),
            ),
            TierZeroCode.TERM_MATCH_REQUIRES_MODEL,
        ),
        (
            decide_tier_zero(
                InventoryItem(item_id="carve", text="A quoted news report"),
                policy_version=1,
                has_carve_out=True,
            ),
            TierZeroCode.CARVE_OUT_REQUIRES_MODEL,
        ),
    ]

    for result, code in cases:
        assert not result.decided
        assert result.code is code
        assert result.verdict is None
