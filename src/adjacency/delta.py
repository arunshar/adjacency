"""Deterministic comparison between engine verdicts and a blocklist baseline."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from adjacency.contracts import Action, DeltaRow, Verdict


@dataclass(frozen=True, slots=True)
class BaselineDecision:
    action: Action
    matched_terms: tuple[str, ...] = ()


class DeltaEngine:
    """Join one engine verdict and one baseline decision for every item."""

    def compare(
        self,
        verdicts: Iterable[Verdict],
        baseline: Mapping[str, BaselineDecision],
    ) -> tuple[DeltaRow, ...]:
        ordered_verdicts = tuple(verdicts)
        item_ids = [verdict.item_id for verdict in ordered_verdicts]
        duplicate_ids = sorted({item_id for item_id in item_ids if item_ids.count(item_id) > 1})
        if duplicate_ids:
            raise ValueError(f"duplicate verdict item ids: {duplicate_ids}")

        engine_ids = set(item_ids)
        baseline_ids = set(baseline)
        if engine_ids != baseline_ids:
            missing = sorted(engine_ids - baseline_ids)
            extra = sorted(baseline_ids - engine_ids)
            raise ValueError(
                f"engine and baseline item ids differ. missing baseline: {missing}. "
                f"extra baseline: {extra}"
            )

        return tuple(
            DeltaRow(
                item_id=verdict.item_id,
                engine_action=verdict.action,
                baseline_action=baseline[verdict.item_id].action,
                matched_terms=baseline[verdict.item_id].matched_terms,
            )
            for verdict in ordered_verdicts
        )
