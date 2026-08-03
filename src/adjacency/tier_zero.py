"""Conservative zero-cost decisions for obviously clean text inventory."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from adjacency.contracts import Action, InventoryItem, Verdict


class TierZeroCode(StrEnum):
    CLEAN_TEXT_ALLOW = "T0_CLEAN_TEXT_ALLOW"
    MEDIA_REQUIRES_MODEL = "T0_MEDIA_REQUIRES_MODEL"
    EMPTY_TEXT_REQUIRES_REVIEW = "T0_EMPTY_TEXT_REQUIRES_REVIEW"
    TERM_MATCH_REQUIRES_MODEL = "T0_TERM_MATCH_REQUIRES_MODEL"
    CARVE_OUT_REQUIRES_MODEL = "T0_CARVE_OUT_REQUIRES_MODEL"


@dataclass(frozen=True, slots=True)
class TierZeroResult:
    code: TierZeroCode
    verdict: Verdict | None = None

    @property
    def decided(self) -> bool:
        return self.verdict is not None


def decide_tier_zero(
    item: InventoryItem,
    *,
    policy_version: int,
    matched_terms: Sequence[str] = (),
    has_carve_out: bool = False,
) -> TierZeroResult:
    """Allow only nonempty text with no media, risk term, or carve-out signal."""

    if item.has_media:
        return TierZeroResult(TierZeroCode.MEDIA_REQUIRES_MODEL)
    if not item.text.strip():
        return TierZeroResult(TierZeroCode.EMPTY_TEXT_REQUIRES_REVIEW)
    if matched_terms:
        return TierZeroResult(TierZeroCode.TERM_MATCH_REQUIRES_MODEL)
    if has_carve_out:
        return TierZeroResult(TierZeroCode.CARVE_OUT_REQUIRES_MODEL)
    return TierZeroResult(
        TierZeroCode.CLEAN_TEXT_ALLOW,
        Verdict(
            item_id=item.item_id,
            action=Action.ALLOW,
            severity=0,
            confidence=1.0,
            tier=0,
            rationale="Tier 0 deterministic clean-text allow.",
            policy_version=policy_version,
        ),
    )
