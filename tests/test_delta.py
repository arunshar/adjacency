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
