from __future__ import annotations

from dataclasses import replace

import pytest

from adjacency.imagine_signal.auction import (
    AuctionMechanism,
    AuctionScenario,
    BidderContext,
    BidderSpec,
    CreativeSignal,
    LearningMode,
    QueryContext,
    UtilityStatus,
    run_adaptive_robustness,
    run_auction_sensitivity,
    stable_hash,
)


def _bidder(
    bidder_id: str,
    bid: float,
    *,
    predicted_ctr: float,
    true_ctr: float,
    value: float | None,
    eligible: bool = True,
    bid_grid: tuple[float, ...] = (),
) -> BidderSpec:
    return BidderSpec(
        bidder_id=bidder_id,
        fixed_bid=bid,
        contexts=(
            BidderContext(
                context_id="q",
                predicted_ctr=predicted_ctr,
                true_ctr=true_ctr,
                value_per_click=value,
                eligible=eligible,
            ),
        ),
        bid_grid=bid_grid,
    )


def _scenario(
    *,
    mechanism: AuctionMechanism = AuctionMechanism.FIRST_PRICE,
    learning_mode: LearningMode = LearningMode.FIXED_BID,
    variant_predicted_ctr: float = 0.5,
    variant_true_ctr: float = 0.2,
    focal_value: float | None = 4.0,
    competitor_value: float | None = 2.0,
    soft_floor: float | None = None,
    horizon: int = 20,
    burn_in: int = 0,
    seeds: tuple[int, ...] = (1, 2),
) -> AuctionScenario:
    grid = (0.0, 1.0, 2.0) if learning_mode is not LearningMode.FIXED_BID else ()
    return AuctionScenario(
        scenario_id="hand_checked",
        contexts=(QueryContext("q", 1.0),),
        bidders=(
            _bidder(
                "focal",
                2.0,
                predicted_ctr=0.5,
                true_ctr=0.2,
                value=focal_value,
                bid_grid=grid,
            ),
            _bidder(
                "competitor",
                1.0,
                predicted_ctr=0.6,
                true_ctr=0.1,
                value=competitor_value,
                bid_grid=grid,
            ),
        ),
        focal_bidder_id="focal",
        variant_signals=(
            CreativeSignal(
                context_id="q",
                predicted_ctr=variant_predicted_ctr,
                true_ctr=variant_true_ctr,
            ),
        ),
        mechanism=mechanism,
        learning_mode=learning_mode,
        soft_floor=soft_floor,
        horizon=horizon,
        burn_in=burn_in,
        seeds=seeds,
        stability_threshold=1.0,
        data_origin="synthetic_unit_test",
    )


def test_fixed_first_price_hand_computation_and_zero_signal_identity() -> None:
    result = run_auction_sensitivity(_scenario())

    assert result.evidence_class == "E2_SIMULATED"
    assert result.data_origin == "synthetic_unit_test"
    assert result.learning_mode is LearningMode.FIXED_BID
    assert result.baseline.simulated_seller_revenue_per_impression == pytest.approx(0.4)
    assert result.baseline.simulated_advertiser_spend_per_impression == pytest.approx(0.4)
    assert result.baseline.focal_advertiser_utility_per_impression == pytest.approx(0.4)
    assert result.baseline.total_advertiser_utility_per_impression == pytest.approx(0.4)
    assert result.baseline.fill_rate == 1.0
    assert result.baseline.participation_rate == 1.0
    assert result.baseline.winner_concentration_hhi == 1.0
    assert result.delta.simulated_seller_revenue_per_impression == 0.0
    assert result.delta.simulated_advertiser_spend_per_impression == 0.0
    assert result.delta.allocation_change_rate == 0.0
    assert result.delta.focal_boundary_crossing_rate == 0.0
    assert result.baseline_score_distance.mean == pytest.approx(0.4)
    assert result.baseline_evidence_hash == result.variant_evidence_hash
    assert result.baseline_convergence.status == "not_applicable_fixed_bids"
    assert "simulated seller revenue" in result.allowed_claim
    assert "The variant increases X revenue." in result.disallowed_claims

    payload = result.to_dict()
    assert payload["mechanism"] == "first_price"
    assert payload["baseline"]["utility_status"] == "available"


def test_second_price_uses_score_adjusted_competitive_price() -> None:
    result = run_auction_sensitivity(_scenario(mechanism=AuctionMechanism.SECOND_PRICE))

    # Scores are 1.0 and 0.6. The focal winner pays 0.6 / 0.5 = 1.2 per click.
    assert result.baseline.simulated_seller_revenue_per_impression == pytest.approx(0.24)
    assert result.baseline.focal_advertiser_utility_per_impression == pytest.approx(0.56)


@pytest.mark.parametrize(
    ("floor", "expected_price_per_click"),
    [
        (0.5, 1.2),
        (1.5, 1.5),
        (3.0, 2.0),
    ],
)
def test_soft_floor_pricing_branches(floor: float, expected_price_per_click: float) -> None:
    result = run_auction_sensitivity(
        _scenario(mechanism=AuctionMechanism.SOFT_FLOOR, soft_floor=floor)
    )

    assert result.baseline.simulated_seller_revenue_per_impression == pytest.approx(
        0.2 * expected_price_per_click
    )


def test_small_predicted_signal_crosses_the_allocation_boundary() -> None:
    focal = _bidder(
        "focal",
        1.0,
        predicted_ctr=0.59,
        true_ctr=0.2,
        value=3.0,
    )
    competitor = _bidder(
        "competitor",
        1.0,
        predicted_ctr=0.6,
        true_ctr=0.1,
        value=2.0,
    )
    scenario = AuctionScenario(
        scenario_id="boundary",
        contexts=(QueryContext("q", 1.0),),
        bidders=(focal, competitor),
        focal_bidder_id="focal",
        variant_signals=(CreativeSignal("q", predicted_ctr=0.61, true_ctr=0.2),),
        horizon=10,
        seeds=(9,),
    )

    result = run_auction_sensitivity(scenario)

    assert result.baseline.simulated_seller_revenue_per_impression == pytest.approx(0.1)
    assert result.variant.simulated_seller_revenue_per_impression == pytest.approx(0.2)
    assert result.delta.simulated_seller_revenue_per_impression == pytest.approx(0.1)
    assert result.delta.allocation_change_rate == 1.0
    assert result.delta.focal_boundary_crossing_rate == 1.0
    assert result.baseline_score_distance.mean == pytest.approx(-0.01)
    assert result.variant_score_distance.mean == pytest.approx(0.01)
    assert result.delta.mean_focal_score_distance == pytest.approx(0.02)
    context_result = result.context_results[0]
    assert context_result.context_id == "q"
    assert context_result.status == "available"
    assert context_result.observations == 10
    assert context_result.delta is not None
    assert context_result.delta.allocation_change_rate == 1.0


def test_true_ctr_increase_is_monotone_when_winner_and_price_are_fixed() -> None:
    result = run_auction_sensitivity(_scenario(variant_true_ctr=0.3))

    assert result.delta.allocation_change_rate == 0.0
    assert result.delta.simulated_seller_revenue_per_impression == pytest.approx(0.2)
    assert result.delta.focal_advertiser_utility_per_impression == pytest.approx(0.2)
    assert result.delta.simulated_seller_revenue_per_impression > 0.0


def test_seller_revenue_equals_total_spend_by_construction() -> None:
    result = run_auction_sensitivity(_scenario(variant_predicted_ctr=0.7, variant_true_ctr=0.3))

    assert (
        result.baseline.simulated_seller_revenue_per_impression
        == result.baseline.simulated_advertiser_spend_per_impression
    )
    assert (
        result.variant.simulated_seller_revenue_per_impression
        == result.variant.simulated_advertiser_spend_per_impression
    )
    assert (
        result.delta.simulated_seller_revenue_per_impression
        == result.delta.simulated_advertiser_spend_per_impression
    )


def test_missing_values_make_utility_explicitly_unavailable() -> None:
    result = run_auction_sensitivity(_scenario(focal_value=None, competitor_value=None))

    assert result.baseline.utility_status is UtilityStatus.UNAVAILABLE_MISSING_VALUES
    assert result.baseline.focal_advertiser_utility_per_impression is None
    assert result.baseline.total_advertiser_utility_per_impression is None
    assert result.baseline.bidder_utilities is None
    assert result.delta.focal_advertiser_utility_per_impression is None
    assert result.to_dict()["baseline"]["utility_status"] == "unavailable_missing_values"


def test_no_eligible_bidder_has_zero_fill_and_no_concentration() -> None:
    scenario = AuctionScenario(
        scenario_id="no_fill",
        contexts=(QueryContext("q", 1.0),),
        bidders=(
            _bidder(
                "focal",
                1.0,
                predicted_ctr=0.5,
                true_ctr=0.2,
                value=2.0,
                eligible=False,
            ),
            _bidder(
                "competitor",
                1.0,
                predicted_ctr=0.5,
                true_ctr=0.2,
                value=2.0,
                eligible=False,
            ),
        ),
        focal_bidder_id="focal",
        variant_signals=(CreativeSignal("q", 0.6, 0.2),),
        horizon=4,
    )

    result = run_auction_sensitivity(scenario)

    assert result.baseline.fill_rate == 0.0
    assert result.baseline.participation_rate == 0.0
    assert result.baseline.winner_concentration_hhi is None
    assert result.baseline.total_advertiser_utility_per_impression == 0.0
    assert result.baseline_score_distance.count == 0
    assert result.delta.winner_concentration_hhi is None


def test_context_summary_has_explicit_no_samples_state() -> None:
    contexts = (QueryContext("common", 0.999), QueryContext("rare", 0.001))
    bidder_contexts = (
        BidderContext("common", 0.5, 0.2, 2.0),
        BidderContext("rare", 0.5, 0.2, 2.0),
    )
    scenario = AuctionScenario(
        scenario_id="rare_context",
        contexts=contexts,
        bidders=(BidderSpec("focal", 1.0, bidder_contexts),),
        focal_bidder_id="focal",
        variant_signals=(
            CreativeSignal("common", 0.5, 0.2),
            CreativeSignal("rare", 0.6, 0.3),
        ),
        horizon=1,
        seeds=(0,),
    )

    result = run_auction_sensitivity(scenario)

    by_context = {item.context_id: item for item in result.context_results}
    assert by_context["common"].status == "available"
    assert by_context["common"].observations == 1
    assert by_context["rare"].status == "unavailable_no_samples"
    assert by_context["rare"].observations == 0
    assert by_context["rare"].baseline is None
    assert by_context["rare"].delta is None
    payload = result.to_dict()
    assert payload["context_results"][1]["status"] == "unavailable_no_samples"


def test_seeded_result_and_hash_are_deterministic() -> None:
    scenario = _scenario(variant_predicted_ctr=0.7, variant_true_ctr=0.3)

    first = run_auction_sensitivity(scenario)
    second = run_auction_sensitivity(scenario)

    assert first == second
    assert first.to_dict() == second.to_dict()
    assert stable_hash(scenario) == first.scenario_hash
    assert first.repetitions == 2
    assert first.revenue_delta_standard_error == 0.0


@pytest.mark.parametrize(
    "mode",
    [LearningMode.HEDGE_RESEARCH, LearningMode.EXP3_IX_RESEARCH],
)
def test_adaptive_learning_modes_are_seeded_and_research_labeled(
    mode: LearningMode,
) -> None:
    scenario = _scenario(
        learning_mode=mode,
        variant_predicted_ctr=0.55,
        variant_true_ctr=0.25,
        horizon=240,
        burn_in=40,
        seeds=(7, 11),
    )

    first = run_auction_sensitivity(scenario)
    second = run_auction_sensitivity(scenario)

    assert first == second
    assert first.learning_mode is mode
    assert first.baseline_convergence.status == "stable"
    assert first.variant_convergence.status == "stable"
    assert first.baseline_convergence.converged is True
    assert first.variant_convergence.converged is True
    assert first.baseline_convergence.max_total_variation is not None
    assert first.baseline_convergence.observations_per_half == 100
    assert "research-only bidder adaptation" in first.known_limitations
    assert first.baseline.simulated_seller_revenue_per_impression >= 0.0
    assert first.variant.simulated_seller_revenue_per_impression >= 0.0
    assert first.baseline.utility_status is UtilityStatus.AVAILABLE


def test_adaptive_mode_rejects_missing_values() -> None:
    scenario = _scenario(
        learning_mode=LearningMode.HEDGE_RESEARCH,
        focal_value=None,
        horizon=10,
    )

    with pytest.raises(ValueError, match="adaptive modes require value_per_click"):
        run_auction_sensitivity(scenario)


def test_adaptive_robustness_always_reports_both_learners() -> None:
    scenario = _scenario(
        learning_mode=LearningMode.HEDGE_RESEARCH,
        variant_predicted_ctr=0.55,
        variant_true_ctr=0.25,
        horizon=240,
        burn_in=40,
        seeds=(7, 11),
    )

    first = run_adaptive_robustness(scenario)
    second = run_adaptive_robustness(scenario)

    assert first == second
    assert first.evidence_class == "E2_SIMULATED"
    assert first.hedge.learning_mode is LearningMode.HEDGE_RESEARCH
    assert first.exp3_ix.learning_mode is LearningMode.EXP3_IX_RESEARCH
    assert first.all_runs_stable is True
    assert first.status in {
        "research_only_scenario_dependent",
        "review_learner_disagreement",
    }
    assert "Hedge and EXP3-IX" in first.allowed_claim
    assert first.to_dict()["hedge"]["learning_mode"] == "hedge_research"
    assert first.to_dict()["exp3_ix"]["learning_mode"] == "exp3_ix_research"


def test_bidder_and_scenario_inputs_are_normalized_before_hashing() -> None:
    context_a = QueryContext("a", 0.25)
    context_b = QueryContext("b", 0.75)
    focal_a = BidderContext("a", 0.3, 0.2, 1.0)
    focal_b = BidderContext("b", 0.4, 0.3, 1.0)
    other_a = BidderContext("a", 0.2, 0.1, 1.0)
    other_b = BidderContext("b", 0.2, 0.1, 1.0)

    left = AuctionScenario(
        scenario_id="order",
        contexts=(context_b, context_a),
        bidders=(
            BidderSpec("z", 1.0, (other_b, other_a)),
            BidderSpec("a", 1.0, (focal_b, focal_a)),
        ),
        focal_bidder_id="a",
        variant_signals=(
            CreativeSignal("b", 0.5, 0.3),
            CreativeSignal("a", 0.4, 0.2),
        ),
        seeds=(4, 2),
    )
    right = AuctionScenario(
        scenario_id="order",
        contexts=(context_a, context_b),
        bidders=(
            BidderSpec("a", 1.0, (focal_a, focal_b)),
            BidderSpec("z", 1.0, (other_a, other_b)),
        ),
        focal_bidder_id="a",
        variant_signals=(
            CreativeSignal("a", 0.4, 0.2),
            CreativeSignal("b", 0.5, 0.3),
        ),
        seeds=(2, 4),
    )

    assert left == right
    assert stable_hash(left) == stable_hash(right)


def test_identifiers_use_trimmed_nfc_normalization() -> None:
    assert QueryContext(" e\u0301 ", 1.0).context_id == "\u00e9"
    assert CreativeSignal(" e\u0301 ", 0.2, 0.1).context_id == "\u00e9"
    assert (
        _bidder(
            " focal ",
            1.0,
            predicted_ctr=0.2,
            true_ctr=0.1,
            value=1.0,
        ).bidder_id
        == "focal"
    )

    with pytest.raises(ValueError, match="assumptions must be unique"):
        replace(_scenario(), assumptions=("e\u0301", "\u00e9"))


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: QueryContext("q", 0.0), "context probability"),
        (lambda: BidderContext("q", 1.1, 0.2, 1.0), "predicted_ctr"),
        (lambda: BidderContext("q", 0.2, -0.1, 1.0), "true_ctr"),
        (lambda: BidderContext("q", 0.2, 0.1, -1.0), "value_per_click"),
        (
            lambda: BidderSpec(
                "x",
                1.0,
                (
                    BidderContext("q", 0.2, 0.1, 1.0),
                    BidderContext("q", 0.3, 0.1, 1.0),
                ),
            ),
            "context ids",
        ),
        (
            lambda: BidderSpec(
                "x",
                1.0,
                (BidderContext("q", 0.2, 0.1, 1.0),),
                bid_grid=(0.0, 0.0),
            ),
            "bid grid",
        ),
    ],
)
def test_invalid_component_inputs_fail_closed(factory: object, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        factory()  # type: ignore[operator]


def test_invalid_scenario_inputs_fail_closed() -> None:
    valid = _scenario()

    with pytest.raises(ValueError, match="probabilities must sum"):
        replace(valid, contexts=(QueryContext("q", 0.9),))
    with pytest.raises(ValueError, match="focal_bidder_id"):
        replace(valid, focal_bidder_id="missing")
    with pytest.raises(ValueError, match="variant_signals"):
        replace(valid, variant_signals=(CreativeSignal("other", 0.2, 0.2),))
    with pytest.raises(ValueError, match="soft_floor mechanism requires"):
        replace(valid, mechanism=AuctionMechanism.SOFT_FLOOR)
    with pytest.raises(ValueError, match="soft_floor must be omitted"):
        replace(valid, soft_floor=0.5)
    with pytest.raises(ValueError, match="burn_in"):
        replace(valid, burn_in=valid.horizon)
    with pytest.raises(ValueError, match="horizon"):
        replace(valid, horizon=1.5)
    with pytest.raises(ValueError, match="burn_in"):
        replace(valid, burn_in=1.5)
    with pytest.raises(ValueError, match="seeds"):
        replace(valid, seeds=())
    with pytest.raises(ValueError, match="seeds"):
        replace(valid, seeds=(1, "two"))
    with pytest.raises(ValueError, match="bid_grid"):
        replace(valid, learning_mode=LearningMode.HEDGE_RESEARCH)
