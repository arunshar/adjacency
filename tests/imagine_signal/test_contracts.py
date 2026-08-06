"""Malformed-input and invariant tests for all ImagineSignal contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from adjacency.imagine_signal.contracts import (
    AssetState,
    AuctionScenarioRecord,
    AuctionSensitivityRecord,
    BidderModel,
    BrandSpec,
    CampaignSpec,
    ConvergenceRecord,
    CostStatus,
    CreativeAsset,
    DataOrigin,
    EvidenceClass,
    GenerationBudget,
    HumanApproval,
    LockedAttribute,
    MeasurementWindow,
    Mechanism,
    MutationSpec,
    NextAction,
    OutcomeSnapshot,
    SignalDecision,
    SignalEstimate,
    SignalGateResult,
    UncertaintyInterval,
)

pytestmark = pytest.mark.unit

SV = "1"
H0 = "0" * 64
H1 = "1" * 64
H2 = "2" * 64
START = datetime(2026, 8, 1, tzinfo=UTC)
END = datetime(2026, 8, 2, tzinfo=UTC)


def rebuild(model, **updates):
    payload = model.model_dump(mode="python")
    payload.update(updates)
    return type(model)(**payload)


def make_budget() -> GenerationBudget:
    return GenerationBudget(
        schema_version=SV,
        max_calls=4,
        max_images=4,
        max_quality_images=1,
        max_cost_in_usd_ticks=100,
        max_wallclock_ms=1000,
    )


def make_window() -> MeasurementWindow:
    return MeasurementWindow(schema_version=SV, start=START, end=END)


def make_campaign() -> CampaignSpec:
    return CampaignSpec(
        schema_version=SV,
        tenant_id="tenant",
        campaign_id="campaign",
        objective="Increase qualified clicks",
        audience_contexts=("home", "search"),
        measurement_metric="observed.ctr",
        measurement_window=make_window(),
        brand_spec_hash=H0,
        generation_budget=make_budget(),
        created_by="operator",
    )


def make_lock(name: str = "logo", digest: str = H0) -> LockedAttribute:
    return LockedAttribute(schema_version=SV, name=name, value_sha256=digest)


def make_mutation() -> MutationSpec:
    return MutationSpec(
        schema_version=SV,
        tenant_id="tenant",
        mutation_id="mutation",
        family_id="family",
        campaign_id="campaign",
        root_asset_id="root",
        parent_asset_id="root",
        axis="background_tone",
        level="warm",
        locked_attributes=(make_lock(),),
        prompt_template_version="v1",
        prompt_hash=H1,
    )


def make_asset(*, child: bool = False, **updates) -> CreativeAsset:
    values = {
        "schema_version": SV,
        "tenant_id": "tenant",
        "campaign_id": "campaign",
        "creative_id": "child" if child else "root",
        "root_creative_id": "root",
        "parent_creative_id": "root" if child else None,
        "mutation_id": "mutation" if child else None,
        "request_hash": H0,
        "media_sha256": H1,
        "media_type": "image/png",
        "width": 16,
        "height": 9,
        "provider": "xai",
        "provider_model_requested": "model",
        "provider_model_resolved": "model-2026",
        "provider_request_id": "request",
        "moderation_respected": True,
        "cost_in_usd_ticks": 10,
        "cost_status": CostStatus.EXACT,
        "latency_ms": 50,
        "state": AssetState.VERIFIED,
    }
    values.update(updates)
    return CreativeAsset(**values)


def make_outcome(**updates) -> OutcomeSnapshot:
    values = {
        "schema_version": SV,
        "tenant_id": "tenant",
        "campaign_id": "campaign",
        "creative_id": "child",
        "context_id": "home",
        "experiment_id": "experiment",
        "arm_id": "variant",
        "origin": DataOrigin.FROZEN_REPLAY,
        "measurement_start": START,
        "measurement_end": END,
        "attribution_method": "last_touch",
        "impressions": 100,
        "clicks": 10,
        "conversions": 2,
        "advertiser_spend_ticks": 20,
        "attributed_purchase_value_ticks": 40,
        "source_snapshot_id": "snapshot",
        "source_sha256": H2,
        "observed_at": END + timedelta(hours=1),
    }
    values.update(updates)
    return OutcomeSnapshot(**values)


def make_estimate(**updates) -> SignalEstimate:
    values = {
        "schema_version": SV,
        "baseline_creative_id": "root",
        "variant_creative_id": "child",
        "context_id": "home",
        "metric": "observed.ctr",
        "baseline_estimate": 0.5,
        "variant_estimate": 0.6,
        "absolute_delta": 0.1,
        "relative_delta": 0.2,
        "interval_low": 0.0,
        "interval_high": 0.2,
        "method": "wilson",
        "sample_size": 200,
        "evidence_class": EvidenceClass.FROZEN_REPLAY,
        "outcome_snapshot_hashes": (H0, H1),
    }
    values.update(updates)
    return SignalEstimate(**values)


def make_scenario(**updates) -> AuctionScenarioRecord:
    values = {
        "schema_version": SV,
        "scenario_id": "scenario",
        "scenario_version": "v1",
        "query_contexts": ("home", "search"),
        "query_probabilities": (0.4, 0.6),
        "number_of_slots": 1,
        "billing_basis": "per_impression",
        "scoring_rule": "bid_times_ctr",
        "mechanism": Mechanism.FIRST_PRICE,
        "floor_or_reserve": 0.0,
        "bid_grid": (0.5, 1.0),
        "bidder_types": ("focal", "competitor"),
        "value_matrices": ((1.0, 1.2), (0.8, 0.9)),
        "ctr_matrices": ((0.1, 0.2), (0.15, 0.15)),
        "bidder_model": BidderModel.FIXED_BID,
        "horizon": 100,
        "burn_in": 10,
        "seed": 7,
        "data_origin": DataOrigin.SYNTHETIC,
        "known_departures_from_production": ("single slot",),
    }
    values.update(updates)
    return AuctionScenarioRecord(**values)


def make_diagnostics(**updates) -> ConvergenceRecord:
    values = {
        "schema_version": SV,
        "converged": True,
        "iterations": 100,
        "stability_metric": 0.01,
        "notes": (),
    }
    values.update(updates)
    return ConvergenceRecord(**values)


def make_result(**updates) -> AuctionSensitivityRecord:
    values = {
        "schema_version": SV,
        "scenario_hash": H0,
        "baseline_signal_hash": H1,
        "variant_signal_hash": H2,
        "common_randomness_id": "paired-7",
        "mechanism": Mechanism.FIRST_PRICE,
        "bidder_model": BidderModel.FIXED_BID,
        "boundary_crossing_rate": 0.1,
        "allocation_change_rate": 0.1,
        "simulated_seller_revenue_baseline": 1.0,
        "simulated_seller_revenue_variant": 1.1,
        "simulated_advertiser_utility_baseline": 0.4,
        "simulated_advertiser_utility_variant": 0.45,
        "uncertainty": UncertaintyInterval(
            schema_version=SV,
            low=0.0,
            high=0.2,
            method="paired_bootstrap",
        ),
        "convergence_diagnostics": make_diagnostics(),
        "evidence_class": EvidenceClass.SIMULATED,
    }
    values.update(updates)
    return AuctionSensitivityRecord(**values)


def pass_gate(gate: str = "IS8") -> SignalGateResult:
    return SignalGateResult(
        schema_version=SV,
        gate=gate,
        passed=True,
        code=f"{gate}_OK",
    )


def fail_gate(gate: str = "IS8", action: NextAction = NextAction.HOLD) -> SignalGateResult:
    return SignalGateResult(
        schema_version=SV,
        gate=gate,
        passed=False,
        code=f"{gate}_FAILED",
        coerce_to=action,
    )


def test_base_contract_is_strict_frozen_closed_and_normalized():
    budget = make_budget()
    with pytest.raises(ValidationError):
        GenerationBudget(**budget.model_dump(), extra_field=1)
    with pytest.raises(ValidationError):
        GenerationBudget(**{**budget.model_dump(), "max_calls": "4"})
    with pytest.raises(ValidationError):
        budget.max_calls = 5
    normalized = rebuild(make_campaign(), objective="café")
    assert normalized.objective == "café"
    with pytest.raises(ValidationError):
        rebuild(make_campaign(), audience_contexts=["home"])


def test_generation_budget_rejects_quality_count_above_total():
    with pytest.raises(ValidationError, match="max_quality_images"):
        rebuild(make_budget(), max_quality_images=5)


@pytest.mark.parametrize(
    ("start", "end", "message"),
    [
        (START.replace(tzinfo=None), END, "start must include"),
        (START, END.replace(tzinfo=None), "end must include"),
        (END, START, "end must be after"),
    ],
)
def test_measurement_window_rejects_naive_or_unordered_times(start, end, message):
    with pytest.raises(ValidationError, match=message):
        MeasurementWindow(schema_version=SV, start=start, end=end)


def test_campaign_rejects_duplicate_contexts_and_has_a_stable_hash():
    campaign = make_campaign()
    assert campaign.campaign_hash == rebuild(campaign).campaign_hash
    with pytest.raises(ValidationError, match="audience_contexts"):
        rebuild(campaign, audience_contexts=("home", "home"))


def test_brand_rejects_duplicates_and_required_prohibited_overlap():
    brand = BrandSpec(
        schema_version=SV,
        tenant_id="tenant",
        brand_spec_id="brand",
        required_elements=("logo",),
        prohibited_elements=("competitor",),
        source_provenance=("approved brief",),
    )
    assert brand.brand_spec_hash == rebuild(brand).brand_spec_hash
    with pytest.raises(ValidationError, match="must not contain duplicates"):
        rebuild(brand, logo_constraints=("fixed", "fixed"))
    with pytest.raises(ValidationError, match="both required and prohibited"):
        rebuild(brand, prohibited_elements=("logo",))


def test_mutation_rejects_duplicate_locks_and_axis_lock():
    mutation = make_mutation()
    assert mutation.mutation_hash == rebuild(mutation).mutation_hash
    with pytest.raises(ValidationError, match="must not contain duplicates"):
        rebuild(mutation, locked_attributes=(make_lock(), make_lock()))
    with pytest.raises(ValidationError, match="mutable axis"):
        rebuild(mutation, locked_attributes=(make_lock("background_tone"),))


@pytest.mark.parametrize(
    ("child", "updates", "message"),
    [
        (False, {"parent_creative_id": "parent"}, "root creative cannot have"),
        (True, {"parent_creative_id": None}, "non-root creative requires a parent"),
        (True, {"parent_creative_id": "child"}, "own parent"),
        (False, {"mutation_id": "mutation"}, "root creative cannot carry"),
        (True, {"mutation_id": None}, "non-root creative requires a mutation"),
        (
            False,
            {"cost_status": CostStatus.UNKNOWN, "cost_in_usd_ticks": 1},
            "unknown cost",
        ),
        (
            False,
            {"cost_status": CostStatus.EXACT, "cost_in_usd_ticks": None},
            "known or estimated cost",
        ),
    ],
)
def test_asset_rejects_incoherent_lineage_and_cost(child, updates, message):
    with pytest.raises(ValidationError, match=message):
        make_asset(child=child, **updates)


def test_asset_hash_is_stable_and_unknown_cost_is_explicit():
    asset = make_asset(cost_status=CostStatus.UNKNOWN, cost_in_usd_ticks=None)
    assert asset.asset_hash == rebuild(asset).asset_hash


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"measurement_start": START.replace(tzinfo=None)}, "measurement_start"),
        ({"measurement_end": END.replace(tzinfo=None)}, "measurement_end"),
        ({"observed_at": END.replace(tzinfo=None)}, "observed_at"),
        ({"measurement_start": END, "measurement_end": START}, "must be after"),
        ({"observed_at": START}, "cannot precede"),
        ({"impressions": 5, "clicks": 6}, "clicks cannot exceed"),
        ({"impressions": 5, "clicks": 5, "conversions": 6}, "conversions cannot exceed"),
    ],
)
def test_outcome_rejects_invalid_windows_and_counts(updates, message):
    with pytest.raises(ValidationError, match=message):
        make_outcome(**updates)


def test_outcome_hash_is_stable():
    snapshot = make_outcome()
    assert snapshot.snapshot_hash == rebuild(snapshot).snapshot_hash


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"baseline_estimate": float("nan")}, "must be finite"),
        ({"absolute_delta": 0.2}, "must equal"),
        ({"interval_low": 0.3, "interval_high": 0.2}, "cannot be below"),
        ({"interval_low": 0.11}, "must contain"),
        (
            {"baseline_estimate": 0.0, "variant_estimate": 0.1, "relative_delta": 1.0},
            "must be null",
        ),
        ({"relative_delta": None}, "inconsistent"),
        ({"relative_delta": 0.3}, "inconsistent"),
        ({"outcome_snapshot_hashes": (H0, H0)}, "must not contain duplicates"),
    ],
)
def test_signal_estimate_rejects_incoherent_values(updates, message):
    with pytest.raises(ValidationError, match=message):
        make_estimate(**updates)


def test_zero_baseline_accepts_null_relative_delta_and_hashes_stably():
    estimate = make_estimate(
        baseline_estimate=0.0,
        variant_estimate=0.1,
        absolute_delta=0.1,
        relative_delta=None,
    )
    assert estimate.signal_hash == rebuild(estimate).signal_hash


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"query_probabilities": (1.0,)}, "must align"),
        ({"query_probabilities": (float("nan"), 1.0)}, "finite and non-negative"),
        ({"query_probabilities": (0.2, 0.2)}, "sum to one"),
        ({"number_of_slots": 3}, "cannot exceed bidder"),
        ({"value_matrices": ((1.0, 1.0),)}, "one row per bidder"),
        ({"value_matrices": ((1.0,), (1.0, 1.0))}, "one value per query"),
        ({"ctr_matrices": ((0.1,), (0.1, 0.1))}, "one value per query"),
        ({"value_matrices": ((-1.0, 1.0), (1.0, 1.0))}, "finite and non-negative"),
        ({"ctr_matrices": ((1.1, 0.1), (0.1, 0.1))}, "cannot exceed one"),
        ({"bid_grid": (float("inf"),)}, "finite and non-negative"),
        ({"burn_in": 100}, "less than horizon"),
        (
            {"known_departures_from_production": ("single slot", "single slot")},
            "must not contain duplicates",
        ),
        ({"query_contexts": ("home", "home")}, "query_contexts"),
        ({"bidder_types": ("focal", "focal")}, "bidder_types"),
    ],
)
def test_auction_scenario_rejects_invalid_dimensions_and_values(updates, message):
    with pytest.raises(ValidationError, match=message):
        make_scenario(**updates)


def test_auction_scenario_hash_is_stable():
    scenario = make_scenario()
    assert scenario.scenario_hash == rebuild(scenario).scenario_hash


@pytest.mark.parametrize(
    ("low", "high", "message"),
    [
        (float("nan"), 1.0, "must be finite"),
        (2.0, 1.0, "cannot be below"),
    ],
)
def test_uncertainty_interval_rejects_nonfinite_or_unordered_bounds(low, high, message):
    with pytest.raises(ValidationError, match=message):
        UncertaintyInterval(schema_version=SV, low=low, high=high, method="paired")


def test_convergence_diagnostics_rejects_nonfinite_stability():
    assert make_diagnostics(stability_metric=None).stability_metric is None
    with pytest.raises(ValidationError, match="must be finite"):
        make_diagnostics(stability_metric=float("inf"))


def test_auction_result_is_simulated_finite_and_hashable():
    result = make_result()
    assert result.result_hash == rebuild(result).result_hash
    with pytest.raises(ValidationError, match="must be SIMULATED"):
        make_result(evidence_class=EvidenceClass.SHADOW_ESTIMATE)
    with pytest.raises(ValidationError, match="must be finite"):
        make_result(simulated_seller_revenue_variant=float("inf"))


def test_gate_result_enforces_stable_prefix_and_fail_closed_shape():
    assert bool(pass_gate())
    assert not bool(fail_gate())
    with pytest.raises(ValidationError, match="same IS prefix"):
        SignalGateResult(
            schema_version=SV,
            gate="IS8",
            passed=False,
            code="IS7_FAILED",
            coerce_to=NextAction.HOLD,
        )
    with pytest.raises(ValidationError, match="passing gate"):
        SignalGateResult(
            schema_version=SV,
            gate="IS8",
            passed=True,
            code="IS8_FAILED",
        )
    with pytest.raises(ValidationError, match="cannot coerce"):
        SignalGateResult(
            schema_version=SV,
            gate="IS8",
            passed=True,
            code="IS8_OK",
            coerce_to=NextAction.HOLD,
        )
    with pytest.raises(ValidationError, match="cannot use an OK"):
        SignalGateResult(
            schema_version=SV,
            gate="IS8",
            passed=False,
            code="IS8_OK",
            coerce_to=NextAction.HOLD,
        )
    with pytest.raises(ValidationError, match="must declare"):
        SignalGateResult(
            schema_version=SV,
            gate="IS8",
            passed=False,
            code="IS8_FAILED",
        )


def test_human_approval_requires_an_aware_timestamp():
    values = {
        "schema_version": SV,
        "approval_id": "approval",
        "receipt_id": "receipt",
        "previous_receipt_sha256": H0,
        "actor_id": "reviewer",
        "authorized_action": NextAction.HOLD,
        "reason_code": "REVIEWED",
        "approved_at": END,
    }
    assert HumanApproval(**values).approved_at == END
    with pytest.raises(ValidationError, match="must include"):
        HumanApproval(**{**values, "approved_at": END.replace(tzinfo=None)})


def test_signal_decision_requires_is8_unique_gates_and_derived_final_action():
    decision = SignalDecision(
        schema_version=SV,
        evidence_class=EvidenceClass.SIMULATED,
        proposed_action=NextAction.TEST,
        final_action=NextAction.HOLD,
        gate_results=(pass_gate("IS0"), fail_gate("IS8")),
        claim_wording="simulation only",
        rationale="display only",
    )
    assert decision.decision_hash == rebuild(decision).decision_hash
    with pytest.raises(ValidationError, match="must not contain duplicates"):
        rebuild(decision, gate_results=(fail_gate(), fail_gate()))
    with pytest.raises(ValidationError, match="must include"):
        rebuild(decision, gate_results=(pass_gate("IS0"),))
    with pytest.raises(ValidationError, match="does not match"):
        rebuild(decision, final_action=NextAction.TEST)
