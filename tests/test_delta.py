from __future__ import annotations

import pytest

from adjacency.contracts import Action, DeltaKind, Verdict
from adjacency.delta import BaselineDecision, DeltaEngine


def verdict(item_id: str, action: Action) -> Verdict:
    severity = {Action.ALLOW: 0, Action.REVIEW: 2, Action.BLOCK: 4}[action]
    return Verdict(
        item_id=item_id,
        action=action,
        severity=severity,
        confidence=0.9,
        policy_version=1,
    )


def test_delta_engine_emits_all_three_kinds_in_verdict_order():
    rows = DeltaEngine().compare(
        [
            verdict("agree", Action.ALLOW),
            verdict("over", Action.ALLOW),
            verdict("under", Action.BLOCK),
        ],
        {
            "under": BaselineDecision(Action.ALLOW),
            "agree": BaselineDecision(Action.ALLOW),
            "over": BaselineDecision(Action.BLOCK, ("drug", "sale")),
        },
    )

    assert [row.item_id for row in rows] == ["agree", "over", "under"]
    assert [row.kind for row in rows] == [
        DeltaKind.AGREE,
        DeltaKind.OVER_BLOCK,
        DeltaKind.UNDER_BLOCK,
    ]
    assert rows[1].matched_terms == ("drug", "sale")


@pytest.mark.parametrize(
    ("engine_action", "baseline_action", "expected"),
    (
        (Action.ALLOW, Action.ALLOW, DeltaKind.AGREE),
        (Action.ALLOW, Action.REVIEW, DeltaKind.OVER_BLOCK),
        (Action.ALLOW, Action.BLOCK, DeltaKind.OVER_BLOCK),
        (Action.REVIEW, Action.ALLOW, DeltaKind.UNDER_BLOCK),
        (Action.REVIEW, Action.REVIEW, DeltaKind.AGREE),
        (Action.REVIEW, Action.BLOCK, DeltaKind.AGREE),
        (Action.BLOCK, Action.ALLOW, DeltaKind.UNDER_BLOCK),
        (Action.BLOCK, Action.REVIEW, DeltaKind.AGREE),
        (Action.BLOCK, Action.BLOCK, DeltaKind.AGREE),
    ),
)
def test_delta_kind_compares_immediate_delivery_disposition(
    engine_action, baseline_action, expected
):
    row = DeltaEngine().compare(
        [verdict("item", engine_action)],
        {"item": BaselineDecision(baseline_action)},
    )[0]

    assert row.kind is expected


def test_delta_engine_rejects_duplicate_or_unpaired_item_ids():
    engine = DeltaEngine()
    repeated = verdict("same", Action.ALLOW)

    with pytest.raises(ValueError, match="duplicate verdict"):
        engine.compare([repeated, repeated], {"same": BaselineDecision(Action.ALLOW)})

    with pytest.raises(ValueError, match="missing baseline.*extra baseline"):
        engine.compare(
            [verdict("engine-only", Action.ALLOW)],
            {"baseline-only": BaselineDecision(Action.ALLOW)},
        )
