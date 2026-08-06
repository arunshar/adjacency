"""Deterministic auction sensitivity simulation for ImagineSignal.

This module is intentionally isolated from production auction systems. It accepts an
explicit synthetic or replayed scenario and returns E2 simulation evidence. It never
publishes a ranking signal, changes a bid, or reports simulated revenue as billed revenue.

The fixed-bid mode is the MVP. Hedge and EXP3-IX are research-only implementations of
the single-type, fixed-targeting subset of the learning model in Chen, Nabi, and
Siniscalchi (arXiv:2307.11732v2). Both adaptive modes are exposed so callers cannot
silently report only the favorable learner.
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass, fields, is_dataclass, replace
from enum import Enum, StrEnum
from typing import Any

from adjacency.imagine_signal.canonical import content_sha256, normalize_text

AUCTION_MODEL_VERSION = "0.1.0"
SIMULATION_EVIDENCE_CLASS = "E2_SIMULATED"


class AuctionMechanism(StrEnum):
    """Supported single-slot, pay-per-click pricing mechanisms."""

    FIRST_PRICE = "first_price"
    SECOND_PRICE = "second_price"
    SOFT_FLOOR = "soft_floor"


class LearningMode(StrEnum):
    """Bidder behavior modes, with adaptive modes restricted to research use."""

    FIXED_BID = "fixed_bid"
    HEDGE_RESEARCH = "hedge_research"
    EXP3_IX_RESEARCH = "exp3_ix_research"


class UtilityStatus(StrEnum):
    """Whether advertiser utility is identified by the supplied scenario."""

    AVAILABLE = "available"
    UNAVAILABLE_MISSING_VALUES = "unavailable_missing_values"


@dataclass(frozen=True, slots=True)
class QueryContext:
    """A finite query or audience context and its arrival probability."""

    context_id: str
    probability: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "context_id", _normalized_nonempty(self.context_id, "context_id"))
        _require_finite(self.probability, "context probability")
        if self.probability <= 0.0 or self.probability > 1.0:
            raise ValueError("context probability must be in (0, 1]")


@dataclass(frozen=True, slots=True)
class BidderContext:
    """Bidder inputs for one context.

    ``predicted_ctr`` is used by the scoring rule. ``true_ctr`` is used only for
    expected clicks, seller revenue, and advertiser utility. Keeping these values
    separate prevents a response hypothesis from silently becoming a ranking input.
    """

    context_id: str
    predicted_ctr: float
    true_ctr: float
    value_per_click: float | None
    eligible: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "context_id", _normalized_nonempty(self.context_id, "context_id"))
        _require_probability(self.predicted_ctr, "predicted_ctr")
        _require_probability(self.true_ctr, "true_ctr")
        if self.value_per_click is not None:
            _require_nonnegative(self.value_per_click, "value_per_click")
        if not isinstance(self.eligible, bool):
            raise ValueError("eligible must be a bool")


@dataclass(frozen=True, slots=True)
class CreativeSignal:
    """Replacement CTR signals for the focal creative in one context."""

    context_id: str
    predicted_ctr: float
    true_ctr: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "context_id", _normalized_nonempty(self.context_id, "context_id"))
        _require_probability(self.predicted_ctr, "predicted_ctr")
        _require_probability(self.true_ctr, "true_ctr")


@dataclass(frozen=True, slots=True)
class BidderSpec:
    """One bidder with a fixed target set and optional adaptive bid grid."""

    bidder_id: str
    fixed_bid: float
    contexts: tuple[BidderContext, ...]
    bid_grid: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "bidder_id", _normalized_nonempty(self.bidder_id, "bidder_id"))
        _require_nonnegative(self.fixed_bid, "fixed_bid")
        normalized_contexts = tuple(sorted(tuple(self.contexts), key=lambda item: item.context_id))
        if not normalized_contexts:
            raise ValueError("every bidder must define at least one context")
        _require_unique(
            (item.context_id for item in normalized_contexts),
            f"context ids for bidder {self.bidder_id}",
        )
        object.__setattr__(self, "contexts", normalized_contexts)

        normalized_grid = tuple(sorted(float(value) for value in self.bid_grid))
        for bid in normalized_grid:
            _require_nonnegative(bid, "bid_grid value")
        _require_unique(normalized_grid, f"bid grid for bidder {self.bidder_id}")
        object.__setattr__(self, "bid_grid", normalized_grid)


@dataclass(frozen=True, slots=True)
class AuctionScenario:
    """Fully disclosed single-slot auction sensitivity scenario.

    The scenario represents one baseline creative and one focal variant. Only the
    focal bidder's CTR signals may change. Bids, query draws, competitors, target
    eligibility, pricing, and random draws are paired across both worlds.
    """

    scenario_id: str
    contexts: tuple[QueryContext, ...]
    bidders: tuple[BidderSpec, ...]
    focal_bidder_id: str
    variant_signals: tuple[CreativeSignal, ...]
    mechanism: AuctionMechanism = AuctionMechanism.FIRST_PRICE
    learning_mode: LearningMode = LearningMode.FIXED_BID
    soft_floor: float | None = None
    horizon: int = 10_000
    burn_in: int = 0
    seeds: tuple[int, ...] = (0,)
    hedge_temperature: float = 0.05
    exp3_eta: float = 0.05
    exp3_gamma: float = 0.01
    stability_threshold: float = 0.10
    data_origin: str = "synthetic"
    baseline_evidence_id: str | None = None
    variant_evidence_id: str | None = None
    assumptions: tuple[str, ...] = ()
    known_limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "scenario_id",
            _normalized_nonempty(self.scenario_id, "scenario_id"),
        )
        object.__setattr__(
            self,
            "focal_bidder_id",
            _normalized_nonempty(self.focal_bidder_id, "focal_bidder_id"),
        )
        object.__setattr__(
            self,
            "data_origin",
            _normalized_nonempty(self.data_origin, "data_origin"),
        )

        try:
            mechanism = AuctionMechanism(self.mechanism)
        except ValueError as error:
            raise ValueError(f"unsupported mechanism: {self.mechanism}") from error
        try:
            learning_mode = LearningMode(self.learning_mode)
        except ValueError as error:
            raise ValueError(f"unsupported learning mode: {self.learning_mode}") from error
        object.__setattr__(self, "mechanism", mechanism)
        object.__setattr__(self, "learning_mode", learning_mode)

        normalized_contexts = tuple(sorted(tuple(self.contexts), key=lambda item: item.context_id))
        if not normalized_contexts:
            raise ValueError("scenario must contain at least one context")
        _require_unique((item.context_id for item in normalized_contexts), "scenario context ids")
        probability_sum = math.fsum(item.probability for item in normalized_contexts)
        if not math.isclose(probability_sum, 1.0, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("context probabilities must sum to 1")
        object.__setattr__(self, "contexts", normalized_contexts)

        normalized_bidders = tuple(sorted(tuple(self.bidders), key=lambda item: item.bidder_id))
        if not normalized_bidders:
            raise ValueError("scenario must contain at least one bidder")
        _require_unique((item.bidder_id for item in normalized_bidders), "bidder ids")
        bidder_ids = {item.bidder_id for item in normalized_bidders}
        if self.focal_bidder_id not in bidder_ids:
            raise ValueError("focal_bidder_id must identify a scenario bidder")
        object.__setattr__(self, "bidders", normalized_bidders)

        context_ids = {item.context_id for item in normalized_contexts}
        for bidder in normalized_bidders:
            bidder_context_ids = {item.context_id for item in bidder.contexts}
            if bidder_context_ids != context_ids:
                raise ValueError(
                    f"bidder {bidder.bidder_id} must define exactly the scenario contexts"
                )
            if learning_mode is not LearningMode.FIXED_BID and not bidder.bid_grid:
                raise ValueError("adaptive modes require a nonempty bid_grid for every bidder")

        normalized_variant = tuple(
            sorted(tuple(self.variant_signals), key=lambda item: item.context_id)
        )
        _require_unique((item.context_id for item in normalized_variant), "variant context ids")
        if {item.context_id for item in normalized_variant} != context_ids:
            raise ValueError("variant_signals must define exactly the scenario contexts")
        object.__setattr__(self, "variant_signals", normalized_variant)

        if mechanism is AuctionMechanism.SOFT_FLOOR:
            if self.soft_floor is None:
                raise ValueError("soft_floor mechanism requires a soft_floor value")
            _require_nonnegative(self.soft_floor, "soft_floor")
        elif self.soft_floor is not None:
            raise ValueError(
                "soft_floor must be omitted for first-price and second-price scenarios"
            )

        if not isinstance(self.horizon, int) or isinstance(self.horizon, bool) or self.horizon <= 0:
            raise ValueError("horizon must be a positive integer")
        if (
            not isinstance(self.burn_in, int)
            or isinstance(self.burn_in, bool)
            or self.burn_in < 0
            or self.burn_in >= self.horizon
        ):
            raise ValueError("burn_in must be an integer in [0, horizon)")
        normalized_seeds = tuple(self.seeds)
        if not normalized_seeds:
            raise ValueError("seeds must contain at least one integer")
        if any(not isinstance(seed, int) or isinstance(seed, bool) for seed in normalized_seeds):
            raise ValueError("seeds must contain only integers")
        normalized_seeds = tuple(sorted(normalized_seeds))
        _require_unique(normalized_seeds, "seeds")
        object.__setattr__(self, "seeds", normalized_seeds)

        _require_positive(self.hedge_temperature, "hedge_temperature")
        _require_positive(self.exp3_eta, "exp3_eta")
        _require_positive(self.exp3_gamma, "exp3_gamma")
        _require_probability(self.stability_threshold, "stability_threshold")
        if self.baseline_evidence_id is not None:
            object.__setattr__(
                self,
                "baseline_evidence_id",
                _normalized_nonempty(self.baseline_evidence_id, "baseline_evidence_id"),
            )
        if self.variant_evidence_id is not None:
            object.__setattr__(
                self,
                "variant_evidence_id",
                _normalized_nonempty(self.variant_evidence_id, "variant_evidence_id"),
            )
        assumptions = tuple(_normalized_nonempty(value, "assumption") for value in self.assumptions)
        known_limitations = tuple(
            _normalized_nonempty(value, "known limitation") for value in self.known_limitations
        )
        _require_unique(assumptions, "assumptions")
        _require_unique(known_limitations, "known_limitations")
        object.__setattr__(self, "assumptions", assumptions)
        object.__setattr__(self, "known_limitations", known_limitations)


@dataclass(frozen=True, slots=True)
class BidderUtility:
    bidder_id: str
    utility_per_impression: float


@dataclass(frozen=True, slots=True)
class AuctionRunSummary:
    """Aggregate simulated outcomes for one creative world."""

    simulated_seller_revenue_per_impression: float
    simulated_advertiser_spend_per_impression: float
    fill_rate: float
    mean_eligible_bidders: float
    participation_rate: float
    winner_concentration_hhi: float | None
    focal_advertiser_utility_per_impression: float | None
    total_advertiser_utility_per_impression: float | None
    bidder_utilities: tuple[BidderUtility, ...] | None
    utility_status: UtilityStatus


@dataclass(frozen=True, slots=True)
class ScoreDistanceSummary:
    """Distribution of focal score minus the highest eligible competitor score."""

    count: int
    mean: float | None
    minimum: float | None
    p10: float | None
    median: float | None
    p90: float | None
    maximum: float | None


@dataclass(frozen=True, slots=True)
class SensitivityDelta:
    """Paired variant-minus-baseline simulation deltas."""

    simulated_seller_revenue_per_impression: float
    simulated_advertiser_spend_per_impression: float
    fill_rate: float
    participation_rate: float
    winner_concentration_hhi: float | None
    focal_advertiser_utility_per_impression: float | None
    total_advertiser_utility_per_impression: float | None
    allocation_change_rate: float
    focal_boundary_crossing_rate: float
    mean_focal_score_distance: float | None


@dataclass(frozen=True, slots=True)
class ContextSensitivityResult:
    """Paired metrics for one query context, or an explicit no-samples state."""

    context_id: str
    observations: int
    status: str
    baseline: AuctionRunSummary | None
    variant: AuctionRunSummary | None
    delta: SensitivityDelta | None
    baseline_score_distance: ScoreDistanceSummary
    variant_score_distance: ScoreDistanceSummary


@dataclass(frozen=True, slots=True)
class ConvergenceDiagnostics:
    """Action-distribution stability over two halves of the evaluation window."""

    status: str
    converged: bool | None
    max_total_variation: float | None
    threshold: float
    observations_per_half: int


@dataclass(frozen=True, slots=True)
class AuctionSensitivityResult:
    """Receipt-like E2 auction sensitivity result."""

    scenario_id: str
    scenario_hash: str
    code_version: str
    evidence_class: str
    data_origin: str
    mechanism: AuctionMechanism
    learning_mode: LearningMode
    seeds: tuple[int, ...]
    repetitions: int
    horizon: int
    burn_in: int
    common_randomness_id: str
    baseline_evidence_hash: str
    variant_evidence_hash: str
    baseline: AuctionRunSummary
    variant: AuctionRunSummary
    delta: SensitivityDelta
    baseline_score_distance: ScoreDistanceSummary
    variant_score_distance: ScoreDistanceSummary
    context_results: tuple[ContextSensitivityResult, ...]
    revenue_delta_standard_error: float | None
    baseline_convergence: ConvergenceDiagnostics
    variant_convergence: ConvergenceDiagnostics
    assumptions: tuple[str, ...]
    known_limitations: tuple[str, ...]
    allowed_claim: str
    disallowed_claims: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a stable JSON-compatible representation."""

        value = _to_primitive(self)
        if not isinstance(value, dict):  # pragma: no cover - defensive type guard
            raise TypeError("auction result did not serialize to a dictionary")
        return value


@dataclass(frozen=True, slots=True)
class AdaptiveRobustnessResult:
    """Mandatory paired report for Hedge and EXP3-IX research simulations."""

    scenario_id: str
    scenario_family_hash: str
    evidence_class: str
    hedge: AuctionSensitivityResult
    exp3_ix: AuctionSensitivityResult
    revenue_delta_sign_agreement: bool
    all_runs_stable: bool
    status: str
    allowed_claim: str
    disallowed_claims: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a stable JSON-compatible representation."""

        value = _to_primitive(self)
        if not isinstance(value, dict):  # pragma: no cover - defensive type guard
            raise TypeError("adaptive robustness result did not serialize to a dictionary")
        return value


@dataclass(frozen=True, slots=True)
class _AuctionOutcome:
    context_id: str
    winner_id: str | None
    price_per_click: float
    revenue: float
    participant_count: int
    utilities: tuple[tuple[str, float], ...] | None
    focal_margin: float | None


@dataclass(frozen=True, slots=True)
class _WorldTrace:
    outcomes: tuple[_AuctionOutcome, ...]
    action_indices: tuple[tuple[int, ...], ...]


def run_auction_sensitivity(scenario: AuctionScenario) -> AuctionSensitivityResult:
    """Run paired baseline and focal-variant auction simulations.

    Fixed bids are the production-facing MVP analysis. Adaptive modes implement a
    research-only sensitivity check. They model one persistent type per bidder and a
    fixed target set, which is a strict subset of the paper's action space.
    """

    _validate_runtime_requirements(scenario)
    baseline_traces: list[_WorldTrace] = []
    variant_traces: list[_WorldTrace] = []
    seed_deltas: list[float] = []

    for seed in scenario.seeds:
        baseline_trace = _simulate_world(scenario, seed=seed, use_variant=False)
        variant_trace = _simulate_world(scenario, seed=seed, use_variant=True)
        baseline_traces.append(baseline_trace)
        variant_traces.append(variant_trace)
        baseline_revenue = _mean(outcome.revenue for outcome in baseline_trace.outcomes)
        variant_revenue = _mean(outcome.revenue for outcome in variant_trace.outcomes)
        seed_deltas.append(variant_revenue - baseline_revenue)

    baseline_outcomes = tuple(outcome for trace in baseline_traces for outcome in trace.outcomes)
    variant_outcomes = tuple(outcome for trace in variant_traces for outcome in trace.outcomes)
    baseline_summary = _summarize_world(scenario, baseline_outcomes)
    variant_summary = _summarize_world(scenario, variant_outcomes)

    baseline_distances = tuple(
        outcome.focal_margin for outcome in baseline_outcomes if outcome.focal_margin is not None
    )
    variant_distances = tuple(
        outcome.focal_margin for outcome in variant_outcomes if outcome.focal_margin is not None
    )
    baseline_distance_summary = _summarize_distances(baseline_distances)
    variant_distance_summary = _summarize_distances(variant_distances)

    delta = _build_delta(
        scenario,
        baseline_outcomes,
        variant_outcomes,
        baseline_summary,
        variant_summary,
        baseline_distance_summary,
        variant_distance_summary,
    )
    context_results = _summarize_contexts(scenario, baseline_outcomes, variant_outcomes)

    default_assumptions = (
        "single slot",
        "pay per click billing",
        "score equals bid times predicted CTR",
        "expected click revenue uses true CTR",
        "fixed query probabilities",
        "fixed targeting eligibility",
        "seeded priority tie breaking",
        "no budgets or pacing",
    )
    mechanism_assumptions: tuple[str, ...] = ()
    if scenario.mechanism in {
        AuctionMechanism.SECOND_PRICE,
        AuctionMechanism.SOFT_FLOOR,
    }:
        mechanism_assumptions += (
            "competitive cost per click equals runner-up score divided by winner predicted CTR",
        )
    if scenario.mechanism is AuctionMechanism.SOFT_FLOOR:
        mechanism_assumptions += ("soft floor is applied in score-adjusted cost-per-click space",)
    adaptive_limitations: tuple[str, ...] = ()
    if scenario.learning_mode is not LearningMode.FIXED_BID:
        adaptive_limitations = (
            "research-only bidder adaptation",
            "one persistent bidder type",
            "bid-only actions with fixed targeting",
            "stability is not proof of equilibrium convergence",
        )

    scenario_hash = stable_hash(scenario)
    baseline_evidence_hash = scenario.baseline_evidence_id or _signal_hash(
        scenario, use_variant=False
    )
    variant_evidence_hash = scenario.variant_evidence_id or _signal_hash(scenario, use_variant=True)
    delta_value = delta.simulated_seller_revenue_per_impression
    allowed_claim = (
        f"Under scenario {scenario.scenario_id} and bidder mode "
        f"{scenario.learning_mode.value}, the focal signal changed simulated seller "
        f"revenue per impression by {delta_value:.6f}."
    )

    return AuctionSensitivityResult(
        scenario_id=scenario.scenario_id,
        scenario_hash=scenario_hash,
        code_version=AUCTION_MODEL_VERSION,
        evidence_class=SIMULATION_EVIDENCE_CLASS,
        data_origin=scenario.data_origin,
        mechanism=scenario.mechanism,
        learning_mode=scenario.learning_mode,
        seeds=scenario.seeds,
        repetitions=len(scenario.seeds),
        horizon=scenario.horizon,
        burn_in=scenario.burn_in,
        common_randomness_id=stable_hash(
            {
                "scenario_id": scenario.scenario_id,
                "seeds": scenario.seeds,
                "horizon": scenario.horizon,
                "burn_in": scenario.burn_in,
                "tape_version": 1,
            }
        ),
        baseline_evidence_hash=baseline_evidence_hash,
        variant_evidence_hash=variant_evidence_hash,
        baseline=baseline_summary,
        variant=variant_summary,
        delta=delta,
        baseline_score_distance=baseline_distance_summary,
        variant_score_distance=variant_distance_summary,
        context_results=context_results,
        revenue_delta_standard_error=_standard_error(seed_deltas),
        baseline_convergence=_convergence_diagnostics(scenario, baseline_traces),
        variant_convergence=_convergence_diagnostics(scenario, variant_traces),
        assumptions=tuple(
            dict.fromkeys((*default_assumptions, *mechanism_assumptions, *scenario.assumptions))
        ),
        known_limitations=tuple(
            dict.fromkeys(
                (
                    "conditional simulation, not observed X auction evidence",
                    "no production candidate, budget, pacing, or policy stack",
                    *adaptive_limitations,
                    *scenario.known_limitations,
                )
            )
        ),
        allowed_claim=allowed_claim,
        disallowed_claims=(
            "The variant increases X revenue.",
            "The simulation reports billed publisher revenue.",
            "The simulated bidder behavior is a production equilibrium.",
            "The output may be used to change bids, budgets, pacing, ranking, or floors.",
        ),
    )


simulate_auction_sensitivity = run_auction_sensitivity


def run_adaptive_robustness(scenario: AuctionScenario) -> AdaptiveRobustnessResult:
    """Run Hedge and EXP3-IX together so neither learner can be cherry-picked."""

    hedge_scenario = replace(scenario, learning_mode=LearningMode.HEDGE_RESEARCH)
    exp3_scenario = replace(scenario, learning_mode=LearningMode.EXP3_IX_RESEARCH)
    hedge = run_auction_sensitivity(hedge_scenario)
    exp3_ix = run_auction_sensitivity(exp3_scenario)

    hedge_delta = hedge.delta.simulated_seller_revenue_per_impression
    exp3_delta = exp3_ix.delta.simulated_seller_revenue_per_impression
    sign_agreement = _sign(hedge_delta) == _sign(exp3_delta)
    all_runs_stable = all(
        diagnostics.converged is True
        for diagnostics in (
            hedge.baseline_convergence,
            hedge.variant_convergence,
            exp3_ix.baseline_convergence,
            exp3_ix.variant_convergence,
        )
    )
    if not all_runs_stable:
        status = "review_nonconverged"
    elif not sign_agreement:
        status = "review_learner_disagreement"
    else:
        status = "research_only_scenario_dependent"

    scenario_family = _to_primitive(scenario)
    if not isinstance(scenario_family, dict):  # pragma: no cover - dataclass invariant
        raise TypeError("scenario did not serialize to a dictionary")
    scenario_family["learning_mode"] = "paired_adaptive_research"
    direction = "agreed" if sign_agreement else "disagreed"
    return AdaptiveRobustnessResult(
        scenario_id=scenario.scenario_id,
        scenario_family_hash=stable_hash(scenario_family),
        evidence_class=SIMULATION_EVIDENCE_CLASS,
        hedge=hedge,
        exp3_ix=exp3_ix,
        revenue_delta_sign_agreement=sign_agreement,
        all_runs_stable=all_runs_stable,
        status=status,
        allowed_claim=(
            f"Under scenario {scenario.scenario_id}, Hedge and EXP3-IX {direction} on the "
            "direction of the simulated seller-revenue change."
        ),
        disallowed_claims=(
            "Either learner alone supports a production recommendation.",
            "Learner agreement establishes an X revenue effect.",
            "A stable action distribution proves equilibrium convergence.",
        ),
    )


def stable_hash(value: Any) -> str:
    """Hash a value after deterministic JSON normalization."""

    return content_sha256(_to_primitive(value))


def _validate_runtime_requirements(scenario: AuctionScenario) -> None:
    if scenario.learning_mode is LearningMode.FIXED_BID:
        return
    missing_values = [
        f"{bidder.bidder_id}:{context.context_id}"
        for bidder in scenario.bidders
        for context in bidder.contexts
        if context.value_per_click is None
    ]
    if missing_values:
        raise ValueError(
            "adaptive modes require value_per_click for every bidder context; missing "
            + ", ".join(missing_values)
        )
    for bidder in scenario.bidders:
        max_value = max(context.value_per_click or 0.0 for context in bidder.contexts)
        if max_value + max(bidder.bid_grid) <= 0.0:
            raise ValueError(f"adaptive reward range is zero for bidder {bidder.bidder_id}")


def _simulate_world(
    scenario: AuctionScenario,
    *,
    seed: int,
    use_variant: bool,
) -> _WorldTrace:
    # Reproducible paired simulation, not a security or cryptographic use.
    rng = random.Random(seed)  # nosec B311
    bidder_ids = tuple(bidder.bidder_id for bidder in scenario.bidders)
    action_values = {
        bidder.bidder_id: (
            bidder.bid_grid
            if scenario.learning_mode is not LearningMode.FIXED_BID
            else (bidder.fixed_bid,)
        )
        for bidder in scenario.bidders
    }
    learner_state = {bidder_id: [0.0] * len(action_values[bidder_id]) for bidder_id in bidder_ids}
    chosen_history: list[list[int]] = [[] for _ in bidder_ids]
    outcomes: list[_AuctionOutcome] = []

    for period in range(scenario.horizon):
        context_id = _sample_context(scenario.contexts, rng.random())
        action_uniforms = {bidder_id: rng.random() for bidder_id in bidder_ids}
        priorities = {bidder_id: rng.random() for bidder_id in bidder_ids}

        bids: dict[str, float] = {}
        chosen_indices: dict[str, int] = {}
        chosen_probabilities: dict[str, float] = {}
        for bidder_id in bidder_ids:
            probabilities = _action_probabilities(
                learner_state[bidder_id],
                scenario.learning_mode,
                hedge_temperature=scenario.hedge_temperature,
                exp3_eta=scenario.exp3_eta,
            )
            chosen_index = _sample_index(probabilities, action_uniforms[bidder_id])
            chosen_indices[bidder_id] = chosen_index
            chosen_probabilities[bidder_id] = probabilities[chosen_index]
            bids[bidder_id] = action_values[bidder_id][chosen_index]

        outcome = _run_single_auction(
            scenario,
            context_id=context_id,
            bids=bids,
            priorities=priorities,
            use_variant=use_variant,
        )

        if scenario.learning_mode is LearningMode.HEDGE_RESEARCH:
            for bidder in scenario.bidders:
                bidder_state = learner_state[bidder.bidder_id]
                for action_index, action_bid in enumerate(action_values[bidder.bidder_id]):
                    counterfactual_bids = dict(bids)
                    counterfactual_bids[bidder.bidder_id] = action_bid
                    counterfactual = _run_single_auction(
                        scenario,
                        context_id=context_id,
                        bids=counterfactual_bids,
                        priorities=priorities,
                        use_variant=use_variant,
                    )
                    reward = _normalized_reward(
                        scenario,
                        bidder,
                        counterfactual,
                        action_values[bidder.bidder_id],
                    )
                    bidder_state[action_index] += reward
        elif scenario.learning_mode is LearningMode.EXP3_IX_RESEARCH:
            for bidder in scenario.bidders:
                bidder_id = bidder.bidder_id
                reward = _normalized_reward(
                    scenario,
                    bidder,
                    outcome,
                    action_values[bidder_id],
                )
                action_index = chosen_indices[bidder_id]
                probability = chosen_probabilities[bidder_id]
                estimated_loss = (1.0 - reward) / (probability + scenario.exp3_gamma)
                learner_state[bidder_id][action_index] += estimated_loss

        if period >= scenario.burn_in:
            outcomes.append(outcome)
            for bidder_index, bidder_id in enumerate(bidder_ids):
                chosen_history[bidder_index].append(chosen_indices[bidder_id])

    return _WorldTrace(
        outcomes=tuple(outcomes),
        action_indices=tuple(tuple(history) for history in chosen_history),
    )


def _run_single_auction(
    scenario: AuctionScenario,
    *,
    context_id: str,
    bids: dict[str, float],
    priorities: dict[str, float],
    use_variant: bool,
) -> _AuctionOutcome:
    focal_variant = {item.context_id: item for item in scenario.variant_signals}
    context_by_bidder = {
        bidder.bidder_id: {item.context_id: item for item in bidder.contexts}[context_id]
        for bidder in scenario.bidders
    }

    predicted_ctrs: dict[str, float] = {}
    true_ctrs: dict[str, float] = {}
    for bidder in scenario.bidders:
        bidder_context = context_by_bidder[bidder.bidder_id]
        predicted_ctrs[bidder.bidder_id] = bidder_context.predicted_ctr
        true_ctrs[bidder.bidder_id] = bidder_context.true_ctr
    if use_variant:
        signal = focal_variant[context_id]
        predicted_ctrs[scenario.focal_bidder_id] = signal.predicted_ctr
        true_ctrs[scenario.focal_bidder_id] = signal.true_ctr

    eligible_ids = tuple(
        bidder.bidder_id
        for bidder in scenario.bidders
        if context_by_bidder[bidder.bidder_id].eligible
    )
    competitor_scores = [
        bids[bidder_id] * predicted_ctrs[bidder_id]
        for bidder_id in eligible_ids
        if bidder_id != scenario.focal_bidder_id
    ]
    focal_context = context_by_bidder[scenario.focal_bidder_id]
    focal_margin = None
    if focal_context.eligible:
        focal_score = bids[scenario.focal_bidder_id] * predicted_ctrs[scenario.focal_bidder_id]
        focal_margin = focal_score - (max(competitor_scores) if competitor_scores else 0.0)

    if not eligible_ids:
        return _AuctionOutcome(
            context_id=context_id,
            winner_id=None,
            price_per_click=0.0,
            revenue=0.0,
            participant_count=0,
            utilities=_zero_utilities_if_available(scenario),
            focal_margin=focal_margin,
        )

    ranked = sorted(
        eligible_ids,
        key=lambda bidder_id: (
            -(bids[bidder_id] * predicted_ctrs[bidder_id]),
            -priorities[bidder_id],
            bidder_id,
        ),
    )
    winner_id = ranked[0]
    winner_bid = bids[winner_id]
    winner_predicted_ctr = predicted_ctrs[winner_id]
    second_score = bids[ranked[1]] * predicted_ctrs[ranked[1]] if len(ranked) > 1 else 0.0
    competitive_price = (
        min(winner_bid, second_score / winner_predicted_ctr) if winner_predicted_ctr > 0.0 else 0.0
    )

    if scenario.mechanism is AuctionMechanism.FIRST_PRICE:
        price_per_click = winner_bid
    elif scenario.mechanism is AuctionMechanism.SECOND_PRICE:
        price_per_click = competitive_price
    else:
        floor = scenario.soft_floor
        if floor is None:  # pragma: no cover - guaranteed by scenario validation
            raise ValueError("soft floor is missing")
        if competitive_price >= floor:
            price_per_click = competitive_price
        elif winner_bid >= floor:
            price_per_click = floor
        else:
            price_per_click = winner_bid

    revenue = true_ctrs[winner_id] * price_per_click
    utilities: tuple[tuple[str, float], ...] | None
    if _utility_status(scenario) is UtilityStatus.AVAILABLE:
        values = {
            bidder.bidder_id: context_by_bidder[bidder.bidder_id].value_per_click
            for bidder in scenario.bidders
        }
        winner_value = values[winner_id]
        if winner_value is None:  # pragma: no cover - guarded by utility status
            raise ValueError("winner value is unexpectedly unavailable")
        utilities = tuple(
            (
                bidder.bidder_id,
                true_ctrs[winner_id] * (winner_value - price_per_click)
                if bidder.bidder_id == winner_id
                else 0.0,
            )
            for bidder in scenario.bidders
        )
    else:
        utilities = None

    return _AuctionOutcome(
        context_id=context_id,
        winner_id=winner_id,
        price_per_click=price_per_click,
        revenue=revenue,
        participant_count=len(eligible_ids),
        utilities=utilities,
        focal_margin=focal_margin,
    )


def _normalized_reward(
    scenario: AuctionScenario,
    bidder: BidderSpec,
    outcome: _AuctionOutcome,
    action_values: tuple[float, ...],
) -> float:
    if outcome.utilities is None:
        raise ValueError("adaptive rewards require advertiser values")
    utility = dict(outcome.utilities)[bidder.bidder_id]
    max_value = max(context.value_per_click or 0.0 for context in bidder.contexts)
    max_bid = max(action_values)
    denominator = max_value + max_bid
    if denominator <= 0.0:  # pragma: no cover - guarded by runtime validation
        raise ValueError("adaptive reward denominator must be positive")
    normalized = (utility + max_bid) / denominator
    return min(1.0, max(0.0, normalized))


def _action_probabilities(
    state: list[float],
    mode: LearningMode,
    *,
    hedge_temperature: float,
    exp3_eta: float,
) -> tuple[float, ...]:
    if mode is LearningMode.FIXED_BID:
        return (1.0,)
    if mode is LearningMode.HEDGE_RESEARCH:
        logits = tuple(value / hedge_temperature for value in state)
    else:
        logits = tuple(-exp3_eta * value for value in state)
    return _softmax(logits)


def _softmax(logits: tuple[float, ...]) -> tuple[float, ...]:
    maximum = max(logits)
    exponentials = tuple(math.exp(value - maximum) for value in logits)
    denominator = math.fsum(exponentials)
    return tuple(value / denominator for value in exponentials)


def _sample_context(contexts: tuple[QueryContext, ...], draw: float) -> str:
    cumulative = 0.0
    for context in contexts:
        cumulative += context.probability
        if draw < cumulative:
            return context.context_id
    return contexts[-1].context_id


def _sample_index(probabilities: tuple[float, ...], draw: float) -> int:
    cumulative = 0.0
    for index, probability in enumerate(probabilities):
        cumulative += probability
        if draw < cumulative:
            return index
    return len(probabilities) - 1


def _summarize_world(
    scenario: AuctionScenario,
    outcomes: tuple[_AuctionOutcome, ...],
) -> AuctionRunSummary:
    count = len(outcomes)
    revenue = math.fsum(outcome.revenue for outcome in outcomes) / count
    fills = sum(outcome.winner_id is not None for outcome in outcomes)
    fill_rate = fills / count
    mean_participants = math.fsum(outcome.participant_count for outcome in outcomes) / count
    participation_rate = mean_participants / len(scenario.bidders)
    winner_counts = {
        bidder.bidder_id: sum(outcome.winner_id == bidder.bidder_id for outcome in outcomes)
        for bidder in scenario.bidders
    }
    hhi = None
    if fills:
        hhi = math.fsum((winner_count / fills) ** 2 for winner_count in winner_counts.values())

    status = _utility_status(scenario)
    if status is UtilityStatus.AVAILABLE:
        bidder_utilities = tuple(
            BidderUtility(
                bidder_id=bidder.bidder_id,
                utility_per_impression=math.fsum(
                    dict(outcome.utilities or ())[bidder.bidder_id] for outcome in outcomes
                )
                / count,
            )
            for bidder in scenario.bidders
        )
        utility_by_bidder = {
            item.bidder_id: item.utility_per_impression for item in bidder_utilities
        }
        focal_utility = utility_by_bidder[scenario.focal_bidder_id]
        total_utility = math.fsum(utility_by_bidder.values())
    else:
        bidder_utilities = None
        focal_utility = None
        total_utility = None

    return AuctionRunSummary(
        simulated_seller_revenue_per_impression=revenue,
        simulated_advertiser_spend_per_impression=revenue,
        fill_rate=fill_rate,
        mean_eligible_bidders=mean_participants,
        participation_rate=participation_rate,
        winner_concentration_hhi=hhi,
        focal_advertiser_utility_per_impression=focal_utility,
        total_advertiser_utility_per_impression=total_utility,
        bidder_utilities=bidder_utilities,
        utility_status=status,
    )


def _build_delta(
    scenario: AuctionScenario,
    baseline_outcomes: tuple[_AuctionOutcome, ...],
    variant_outcomes: tuple[_AuctionOutcome, ...],
    baseline_summary: AuctionRunSummary,
    variant_summary: AuctionRunSummary,
    baseline_distance: ScoreDistanceSummary,
    variant_distance: ScoreDistanceSummary,
) -> SensitivityDelta:
    observation_count = len(baseline_outcomes)
    if observation_count == 0 or len(variant_outcomes) != observation_count:
        raise ValueError("paired delta requires equal nonempty outcome sequences")

    allocation_changes = 0
    boundary_crossings = 0
    for baseline_outcome, variant_outcome in zip(
        baseline_outcomes,
        variant_outcomes,
        strict=True,
    ):
        if baseline_outcome.winner_id != variant_outcome.winner_id:
            allocation_changes += 1
        baseline_focal_won = baseline_outcome.winner_id == scenario.focal_bidder_id
        variant_focal_won = variant_outcome.winner_id == scenario.focal_bidder_id
        if baseline_focal_won != variant_focal_won:
            boundary_crossings += 1

    return SensitivityDelta(
        simulated_seller_revenue_per_impression=(
            variant_summary.simulated_seller_revenue_per_impression
            - baseline_summary.simulated_seller_revenue_per_impression
        ),
        simulated_advertiser_spend_per_impression=(
            variant_summary.simulated_advertiser_spend_per_impression
            - baseline_summary.simulated_advertiser_spend_per_impression
        ),
        fill_rate=variant_summary.fill_rate - baseline_summary.fill_rate,
        participation_rate=(
            variant_summary.participation_rate - baseline_summary.participation_rate
        ),
        winner_concentration_hhi=_optional_delta(
            variant_summary.winner_concentration_hhi,
            baseline_summary.winner_concentration_hhi,
        ),
        focal_advertiser_utility_per_impression=_optional_delta(
            variant_summary.focal_advertiser_utility_per_impression,
            baseline_summary.focal_advertiser_utility_per_impression,
        ),
        total_advertiser_utility_per_impression=_optional_delta(
            variant_summary.total_advertiser_utility_per_impression,
            baseline_summary.total_advertiser_utility_per_impression,
        ),
        allocation_change_rate=allocation_changes / observation_count,
        focal_boundary_crossing_rate=boundary_crossings / observation_count,
        mean_focal_score_distance=_optional_delta(
            variant_distance.mean,
            baseline_distance.mean,
        ),
    )


def _summarize_contexts(
    scenario: AuctionScenario,
    baseline_outcomes: tuple[_AuctionOutcome, ...],
    variant_outcomes: tuple[_AuctionOutcome, ...],
) -> tuple[ContextSensitivityResult, ...]:
    results: list[ContextSensitivityResult] = []
    for context in scenario.contexts:
        baseline = tuple(
            outcome for outcome in baseline_outcomes if outcome.context_id == context.context_id
        )
        variant = tuple(
            outcome for outcome in variant_outcomes if outcome.context_id == context.context_id
        )
        if len(baseline) != len(variant):
            raise ValueError("common-randomness context counts must match")

        baseline_distance = _summarize_distances(
            tuple(outcome.focal_margin for outcome in baseline if outcome.focal_margin is not None)
        )
        variant_distance = _summarize_distances(
            tuple(outcome.focal_margin for outcome in variant if outcome.focal_margin is not None)
        )
        if not baseline:
            results.append(
                ContextSensitivityResult(
                    context_id=context.context_id,
                    observations=0,
                    status="unavailable_no_samples",
                    baseline=None,
                    variant=None,
                    delta=None,
                    baseline_score_distance=baseline_distance,
                    variant_score_distance=variant_distance,
                )
            )
            continue

        baseline_summary = _summarize_world(scenario, baseline)
        variant_summary = _summarize_world(scenario, variant)
        results.append(
            ContextSensitivityResult(
                context_id=context.context_id,
                observations=len(baseline),
                status="available",
                baseline=baseline_summary,
                variant=variant_summary,
                delta=_build_delta(
                    scenario,
                    baseline,
                    variant,
                    baseline_summary,
                    variant_summary,
                    baseline_distance,
                    variant_distance,
                ),
                baseline_score_distance=baseline_distance,
                variant_score_distance=variant_distance,
            )
        )
    return tuple(results)


def _summarize_distances(values: tuple[float, ...]) -> ScoreDistanceSummary:
    if not values:
        return ScoreDistanceSummary(0, None, None, None, None, None, None)
    ordered = tuple(sorted(values))
    return ScoreDistanceSummary(
        count=len(ordered),
        mean=math.fsum(ordered) / len(ordered),
        minimum=ordered[0],
        p10=_quantile(ordered, 0.10),
        median=_quantile(ordered, 0.50),
        p90=_quantile(ordered, 0.90),
        maximum=ordered[-1],
    )


def _quantile(ordered: tuple[float, ...], probability: float) -> float:
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _convergence_diagnostics(
    scenario: AuctionScenario,
    traces: list[_WorldTrace],
) -> ConvergenceDiagnostics:
    if scenario.learning_mode is LearningMode.FIXED_BID:
        return ConvergenceDiagnostics(
            status="not_applicable_fixed_bids",
            converged=None,
            max_total_variation=None,
            threshold=scenario.stability_threshold,
            observations_per_half=0,
        )

    evaluation_length = scenario.horizon - scenario.burn_in
    half = evaluation_length // 2
    if half == 0:
        return ConvergenceDiagnostics(
            status="unavailable_insufficient_window",
            converged=None,
            max_total_variation=None,
            threshold=scenario.stability_threshold,
            observations_per_half=0,
        )

    distances: list[float] = []
    for trace in traces:
        for bidder, history in zip(scenario.bidders, trace.action_indices, strict=True):
            first = history[:half]
            second = history[-half:]
            action_count = len(bidder.bid_grid)
            first_distribution = tuple(first.count(index) / half for index in range(action_count))
            second_distribution = tuple(second.count(index) / half for index in range(action_count))
            distances.append(
                0.5
                * math.fsum(
                    abs(left - right)
                    for left, right in zip(
                        first_distribution,
                        second_distribution,
                        strict=True,
                    )
                )
            )
    maximum = max(distances)
    return ConvergenceDiagnostics(
        status="stable" if maximum <= scenario.stability_threshold else "unstable",
        converged=maximum <= scenario.stability_threshold,
        max_total_variation=maximum,
        threshold=scenario.stability_threshold,
        observations_per_half=half,
    )


def _utility_status(scenario: AuctionScenario) -> UtilityStatus:
    if any(
        context.value_per_click is None
        for bidder in scenario.bidders
        for context in bidder.contexts
    ):
        return UtilityStatus.UNAVAILABLE_MISSING_VALUES
    return UtilityStatus.AVAILABLE


def _zero_utilities_if_available(
    scenario: AuctionScenario,
) -> tuple[tuple[str, float], ...] | None:
    if _utility_status(scenario) is UtilityStatus.UNAVAILABLE_MISSING_VALUES:
        return None
    return tuple((bidder.bidder_id, 0.0) for bidder in scenario.bidders)


def _signal_hash(scenario: AuctionScenario, *, use_variant: bool) -> str:
    focal = next(
        bidder for bidder in scenario.bidders if bidder.bidder_id == scenario.focal_bidder_id
    )
    if use_variant:
        signals: Any = scenario.variant_signals
    else:
        signals = tuple(
            CreativeSignal(
                context_id=context.context_id,
                predicted_ctr=context.predicted_ctr,
                true_ctr=context.true_ctr,
            )
            for context in focal.contexts
        )
    return stable_hash(
        {
            "scenario_id": scenario.scenario_id,
            "focal_bidder_id": scenario.focal_bidder_id,
            "signals": signals,
        }
    )


def _standard_error(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    return statistics.stdev(values) / math.sqrt(len(values))


def _optional_delta(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return left - right


def _sign(value: float, *, tolerance: float = 1e-12) -> int:
    if value > tolerance:
        return 1
    if value < -tolerance:
        return -1
    return 0


def _mean(values: Any) -> float:
    realized = tuple(values)
    return math.fsum(realized) / len(realized)


def _to_primitive(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _to_primitive(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {str(key): _to_primitive(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_to_primitive(item) for item in value]
    if isinstance(value, float) and value == 0.0:
        return 0.0
    return value


def _require_nonempty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a nonempty string")


def _normalized_nonempty(value: str, field_name: str) -> str:
    _require_nonempty(value, field_name)
    return normalize_text(value.strip())


def _require_finite(value: float, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric")
    if not math.isfinite(float(value)):
        raise ValueError(f"{field_name} must be finite")


def _require_nonnegative(value: float, field_name: str) -> None:
    _require_finite(value, field_name)
    if value < 0.0:
        raise ValueError(f"{field_name} must be nonnegative")


def _require_positive(value: float, field_name: str) -> None:
    _require_finite(value, field_name)
    if value <= 0.0:
        raise ValueError(f"{field_name} must be positive")


def _require_probability(value: float, field_name: str) -> None:
    _require_finite(value, field_name)
    if value < 0.0 or value > 1.0:
        raise ValueError(f"{field_name} must be in [0, 1]")


def _require_unique(values: Any, field_name: str) -> None:
    realized = tuple(values)
    if len(realized) != len(set(realized)):
        raise ValueError(f"{field_name} must be unique")
