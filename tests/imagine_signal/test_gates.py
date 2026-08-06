"""Exhaustive failure-code tests for the pure IS0 through IS8 gates."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from adjacency.imagine_signal.contracts import (
    AssetState,
    AuctionSensitivityRecord,
    BidderModel,
    CampaignSpec,
    ConvergenceRecord,
    CostStatus,
    CreativeAsset,
    DataOrigin,
    DeploymentMode,
    EvidenceClass,
    GenerationBudget,
    LockedAttribute,
    MeasurementWindow,
    Mechanism,
    NextAction,
    OutcomeSnapshot,
    SignalEstimate,
    UncertaintyInterval,
)
from adjacency.imagine_signal.gates import (
    is0_request_budget,
    is1_lineage,
    is2_controlled_mutation,
    is3_provider_admission,
    is4_asset_integrity,
    is5_outcome_admission,
    is6_statistical_validity,
    is7_auction_sensitivity,
    is8_evidence_action,
)
from adjacency.imagine_signal.mutations import plan_controlled_mutations

pytestmark = pytest.mark.unit

SV = "1"
H0 = "0" * 64
H1 = "1" * 64
H2 = "2" * 64
START = datetime(2026, 8, 1, tzinfo=UTC)
END = datetime(2026, 8, 2, tzinfo=UTC)
NOW = datetime(2026, 8, 3, tzinfo=UTC)


def make_budget(**updates) -> GenerationBudget:
    values = {
        "schema_version": SV,
        "max_calls": 4,
        "max_images": 4,
        "max_quality_images": 1,
        "max_cost_in_usd_ticks": 100,
        "max_wallclock_ms": 1000,
    }
    values.update(updates)
    return GenerationBudget(**values)


def make_campaign(**updates) -> CampaignSpec:
    values = {
        "schema_version": SV,
        "tenant_id": "tenant",
        "campaign_id": "campaign",
        "objective": "test",
        "audience_contexts": ("home",),
        "measurement_metric": "observed.ctr",
        "measurement_window": MeasurementWindow(
            schema_version=SV,
            start=START,
            end=NOW,
        ),
        "brand_spec_hash": H0,
        "generation_budget": make_budget(),
        "created_by": "operator",
    }
    values.update(updates)
    return CampaignSpec(**values)


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
        "provider_model_resolved": "resolved",
        "provider_request_id": "request",
        "moderation_respected": True,
        "cost_in_usd_ticks": 10,
        "cost_status": CostStatus.EXACT,
        "latency_ms": 20,
        "state": AssetState.VERIFIED,
    }
    values.update(updates)
    return CreativeAsset(**values)


def make_mutations():
    return plan_controlled_mutations(
        schema_version=SV,
        tenant_id="tenant",
        family_id="family",
        campaign_id="campaign",
        root_asset_id="root",
        parent_asset_id="root",
        axis="background_tone",
        levels=("warm", "cool"),
        locked_attributes=(LockedAttribute(schema_version=SV, name="logo", value_sha256=H0),),
        prompt_template_version="v1",
        prompt_template="Set {axis} to {level}",
    )


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
        "baseline_estimate": 0.1,
        "variant_estimate": 0.12,
        "absolute_delta": 0.02,
        "relative_delta": 0.2,
        "interval_low": 0.01,
        "interval_high": 0.03,
        "method": "wilson",
        "sample_size": 200,
        "evidence_class": EvidenceClass.FROZEN_REPLAY,
        "outcome_snapshot_hashes": (H0, H1),
    }
    values.update(updates)
    return SignalEstimate(**values)


def make_result(
    *,
    bidder_model: BidderModel = BidderModel.FIXED_BID,
    revenue_delta: float = 0.1,
    converged: bool = True,
    scenario_hash: str = H0,
    randomness_id: str = "paired",
) -> AuctionSensitivityRecord:
    return AuctionSensitivityRecord(
        schema_version=SV,
        scenario_hash=scenario_hash,
        baseline_signal_hash=H1,
        variant_signal_hash=H2,
        common_randomness_id=randomness_id,
        mechanism=Mechanism.FIRST_PRICE,
        bidder_model=bidder_model,
        boundary_crossing_rate=0.1,
        allocation_change_rate=0.1,
        simulated_seller_revenue_baseline=1.0,
        simulated_seller_revenue_variant=1.0 + revenue_delta,
        simulated_advertiser_utility_baseline=0.5,
        simulated_advertiser_utility_variant=0.55,
        uncertainty=UncertaintyInterval(
            schema_version=SV,
            low=-0.1,
            high=0.2,
            method="paired",
        ),
        convergence_diagnostics=ConvergenceRecord(
            schema_version=SV,
            converged=converged,
            iterations=100,
            stability_metric=0.01,
        ),
    )


def is0(**updates):
    values = {
        "mode": DeploymentMode.FIXTURE,
        "allowed_modes": frozenset({DeploymentMode.FIXTURE}),
        "requested_calls": 2,
        "requested_images": 2,
        "requested_quality_images": 1,
        "requested_cost_in_usd_ticks": 50,
        "cost_status": CostStatus.EXACT,
        "elapsed_ms": 500,
        "budget": make_budget(),
        "generation_enabled": True,
        "schema_version": SV,
    }
    values.update(updates)
    return is0_request_budget(**values)


def test_is0_passes_at_or_below_every_cap():
    assert is0().passed
    assert is0(
        requested_calls=4,
        requested_images=4,
        requested_quality_images=1,
        requested_cost_in_usd_ticks=100,
        elapsed_ms=1000,
    ).passed


@pytest.mark.parametrize(
    "updates",
    [
        {"requested_calls": -1},
        {"requested_cost_in_usd_ticks": -1},
    ],
)
def test_is0_rejects_negative_work(updates):
    assert is0(**updates).code == "IS0_REQUEST_INVALID"


def test_is0_honors_kill_switch_and_explicit_mode():
    assert is0(generation_enabled=False).code == "IS0_GENERATION_DISABLED"
    wrong = is0(mode=DeploymentMode.RECORD)
    assert wrong.code == "IS0_MODE_NOT_ALLOWED"
    assert wrong.security_signal
    malformed = is0(mode="fixture")
    assert malformed.code == "IS0_MODE_NOT_ALLOWED"


def test_is0_rejects_quality_count_above_total_and_unknown_cost():
    assert is0(requested_quality_images=3, requested_images=2).code == "IS0_REQUEST_INVALID"
    assert is0(cost_status=CostStatus.UNKNOWN).code == "IS0_COST_UNKNOWN"
    assert is0(requested_cost_in_usd_ticks=None).code == "IS0_COST_UNKNOWN"


def test_is0_reports_all_simultaneous_budget_breaches():
    result = is0(
        requested_calls=5,
        requested_images=6,
        requested_quality_images=2,
        requested_cost_in_usd_ticks=101,
        elapsed_ms=1001,
    )
    assert result.code == "IS0_BUDGET_EXCEEDED"
    for label in ("calls", "images", "quality images", "cost", "wallclock"):
        assert label in result.detail


def test_is1_accepts_a_root_or_valid_child():
    campaign = make_campaign()
    root = make_asset()
    assert is1_lineage(campaign=campaign, child=root, parent=None, schema_version=SV).passed
    child = make_asset(child=True)
    assert is1_lineage(campaign=campaign, child=child, parent=root, schema_version=SV).passed


def test_is1_rejects_campaign_tenant_and_campaign_mismatch():
    campaign = make_campaign()
    result = is1_lineage(
        campaign=campaign,
        child=make_asset(tenant_id="other"),
        parent=None,
        schema_version=SV,
    )
    assert result.code == "IS1_CAMPAIGN_TENANT_MISMATCH"
    assert result.security_signal
    result = is1_lineage(
        campaign=campaign,
        child=make_asset(campaign_id="other"),
        parent=None,
        schema_version=SV,
    )
    assert result.code == "IS1_CAMPAIGN_MISMATCH"


def test_is1_rejects_root_with_parent_and_missing_child_parent():
    campaign = make_campaign()
    assert (
        is1_lineage(
            campaign=campaign,
            child=make_asset(),
            parent=make_asset(),
            schema_version=SV,
        ).code
        == "IS1_ROOT_HAS_PARENT"
    )
    assert (
        is1_lineage(
            campaign=campaign,
            child=make_asset(child=True),
            parent=None,
            schema_version=SV,
        ).code
        == "IS1_PARENT_MISSING"
    )


@pytest.mark.parametrize(
    ("parent_updates", "code", "security"),
    [
        ({"tenant_id": "other"}, "IS1_PARENT_TENANT_MISMATCH", True),
        ({"campaign_id": "other"}, "IS1_PARENT_CAMPAIGN_MISMATCH", False),
        ({"creative_id": "other", "root_creative_id": "other"}, "IS1_PARENT_ID_MISMATCH", False),
        ({"root_creative_id": "other", "creative_id": "other"}, "IS1_PARENT_ID_MISMATCH", False),
    ],
)
def test_is1_rejects_invalid_parent_identity(parent_updates, code, security):
    result = is1_lineage(
        campaign=make_campaign(),
        child=make_asset(child=True),
        parent=make_asset(**parent_updates),
        schema_version=SV,
    )
    assert result.code == code
    assert result.security_signal is security


def test_is1_rejects_root_mismatch_after_parent_id_matches():
    parent = make_asset(
        creative_id="root",
        root_creative_id="other-root",
        parent_creative_id="other-root",
        mutation_id="prior",
    )
    result = is1_lineage(
        campaign=make_campaign(),
        child=make_asset(child=True),
        parent=parent,
        schema_version=SV,
    )
    assert result.code == "IS1_ROOT_MISMATCH"


def test_is2_accepts_one_atom_and_rejects_uncontrolled_output():
    mutations = make_mutations()
    changes = {item.mutation_id: (item.axis,) for item in mutations}
    locks = {item.mutation_id: {"logo": H0} for item in mutations}
    assert is2_controlled_mutation(
        mutations,
        observed_changes=changes,
        observed_locked_hashes=locks,
        schema_version=SV,
    ).passed
    changes[mutations[0].mutation_id] = ("background_tone", "logo")
    result = is2_controlled_mutation(
        mutations,
        observed_changes=changes,
        observed_locked_hashes=locks,
        schema_version=SV,
    )
    assert result.code == "IS2_UNCONTROLLED_MUTATION"
    assert result.coerce_to is NextAction.REVIEW


def test_is3_covers_provider_moderation_quarantine_and_cost_states():
    assert is3_provider_admission(make_asset(), provider_completed=True, schema_version=SV).passed
    assert (
        is3_provider_admission(make_asset(), provider_completed=False, schema_version=SV).code
        == "IS3_PROVIDER_INCOMPLETE"
    )
    assert (
        is3_provider_admission(
            make_asset(state=AssetState.PLANNED),
            provider_completed=True,
            schema_version=SV,
        ).code
        == "IS3_PROVIDER_INCOMPLETE"
    )
    assert (
        is3_provider_admission(
            make_asset(state=AssetState.MODERATION_REJECTED),
            provider_completed=True,
            schema_version=SV,
        ).code
        == "IS3_MODERATION_REJECTED"
    )
    bypass = is3_provider_admission(
        make_asset(moderation_respected=False),
        provider_completed=True,
        schema_version=SV,
    )
    assert bypass.code == "IS3_MODERATION_BYPASS"
    assert bypass.security_signal
    assert (
        is3_provider_admission(
            make_asset(state=AssetState.QUARANTINED),
            provider_completed=True,
            schema_version=SV,
        ).code
        == "IS3_RESPONSE_QUARANTINED"
    )
    assert (
        is3_provider_admission(
            make_asset(cost_status=CostStatus.UNKNOWN, cost_in_usd_ticks=None),
            provider_completed=True,
            schema_version=SV,
        ).code
        == "IS3_COST_UNKNOWN"
    )


def test_is4_checks_digest_shape_dimensions_duplicates_and_state():
    asset = make_asset()
    assert is4_asset_integrity(
        asset,
        computed_media_sha256=H1,
        actual_width=16,
        actual_height=9,
        duplicate_of=None,
        schema_version=SV,
    ).passed
    assert (
        is4_asset_integrity(
            asset,
            computed_media_sha256="short",
            actual_width=16,
            actual_height=9,
            duplicate_of=None,
            schema_version=SV,
        ).code
        == "IS4_COMPUTED_HASH_INVALID"
    )
    assert (
        is4_asset_integrity(
            asset,
            computed_media_sha256="g" * 64,
            actual_width=16,
            actual_height=9,
            duplicate_of=None,
            schema_version=SV,
        ).code
        == "IS4_COMPUTED_HASH_INVALID"
    )
    for width, height in ((0, 9), (16, 0)):
        assert (
            is4_asset_integrity(
                asset,
                computed_media_sha256=H1,
                actual_width=width,
                actual_height=height,
                duplicate_of=None,
                schema_version=SV,
            ).code
            == "IS4_MEDIA_SHAPE_INVALID"
        )
    assert (
        is4_asset_integrity(
            asset,
            computed_media_sha256=H2,
            actual_width=16,
            actual_height=9,
            duplicate_of=None,
            schema_version=SV,
        ).code
        == "IS4_ASSET_HASH_MISMATCH"
    )
    assert (
        is4_asset_integrity(
            asset,
            computed_media_sha256=H1,
            actual_width=15,
            actual_height=9,
            duplicate_of=None,
            schema_version=SV,
        ).code
        == "IS4_DIMENSION_MISMATCH"
    )
    duplicate = is4_asset_integrity(
        asset,
        computed_media_sha256=H1,
        actual_width=16,
        actual_height=9,
        duplicate_of="existing",
        schema_version=SV,
    )
    assert duplicate.code == "IS4_EXACT_DUPLICATE"
    assert duplicate.coerce_to is NextAction.KEEP
    assert (
        is4_asset_integrity(
            make_asset(state=AssetState.DUPLICATE),
            computed_media_sha256=H1,
            actual_width=16,
            actual_height=9,
            duplicate_of=None,
            schema_version=SV,
        ).code
        == "IS4_EXACT_DUPLICATE"
    )
    assert (
        is4_asset_integrity(
            make_asset(state=AssetState.GENERATED),
            computed_media_sha256=H1,
            actual_width=16,
            actual_height=9,
            duplicate_of=None,
            schema_version=SV,
        ).code
        == "IS4_ASSET_NOT_VERIFIED"
    )


def is5(snapshot=None, **updates):
    values = {
        "campaign": make_campaign(),
        "asset": make_asset(child=True),
        "now": NOW,
        "max_staleness": timedelta(days=2),
        "expected_experiment_id": "experiment",
        "expected_arm_id": "variant",
        "complete": True,
        "schema_version": SV,
    }
    values.update(updates)
    return is5_outcome_admission(snapshot or make_outcome(), **values)


def test_is5_accepts_a_complete_fresh_join():
    assert is5().passed


def test_is5_rejects_invalid_clock_config_and_partial_data():
    assert is5(now=NOW.replace(tzinfo=None)).code == "IS5_VALIDATION_CONFIG_INVALID"
    assert is5(max_staleness=timedelta(seconds=-1)).code == "IS5_VALIDATION_CONFIG_INVALID"
    assert is5(complete=False).code == "IS5_OUTCOME_INCOMPLETE"


def test_is5_rejects_tenant_campaign_creative_and_assignment_mismatch():
    tenant = is5(make_outcome(tenant_id="other"))
    assert tenant.code == "IS5_OUTCOME_TENANT_MISMATCH"
    assert tenant.security_signal
    assert is5(make_outcome(campaign_id="other")).code == "IS5_OUTCOME_CAMPAIGN_MISMATCH"
    assert is5(make_outcome(creative_id="other")).code == "IS5_OUTCOME_CREATIVE_MISMATCH"
    assert is5(make_outcome(experiment_id="other")).code == "IS5_EXPERIMENT_ARM_MISMATCH"
    assert is5(make_outcome(arm_id="other")).code == "IS5_EXPERIMENT_ARM_MISMATCH"


def test_is5_rejects_window_future_and_staleness_failures():
    assert (
        is5(make_outcome(measurement_start=START - timedelta(seconds=1))).code
        == "IS5_OUTCOME_WINDOW_MISMATCH"
    )
    assert (
        is5(
            make_outcome(
                measurement_end=NOW + timedelta(hours=1),
                observed_at=NOW + timedelta(hours=2),
            )
        ).code
        == "IS5_OUTCOME_WINDOW_MISMATCH"
    )
    assert is5(make_outcome(observed_at=NOW + timedelta(seconds=1))).code == (
        "IS5_OUTCOME_FROM_FUTURE"
    )
    assert is5(max_staleness=timedelta(hours=1)).code == "IS5_OUTCOME_STALE"


def test_is6_checks_threshold_namespace_sample_and_interval():
    estimate = make_estimate()
    assert is6_statistical_validity(
        estimate,
        min_sample_size=100,
        require_interval_excludes_zero=True,
        schema_version=SV,
    ).passed
    assert (
        is6_statistical_validity(
            estimate,
            min_sample_size=-1,
            require_interval_excludes_zero=False,
            schema_version=SV,
        ).code
        == "IS6_THRESHOLD_INVALID"
    )
    assert (
        is6_statistical_validity(
            make_estimate(metric="ctr"),
            min_sample_size=100,
            require_interval_excludes_zero=False,
            schema_version=SV,
        ).code
        == "IS6_METRIC_NAMESPACE_INVALID"
    )
    assert (
        is6_statistical_validity(
            estimate,
            min_sample_size=201,
            require_interval_excludes_zero=False,
            schema_version=SV,
        ).code
        == "IS6_INSUFFICIENT_EVIDENCE"
    )
    includes_zero = make_estimate(interval_low=-0.01)
    assert (
        is6_statistical_validity(
            includes_zero,
            min_sample_size=100,
            require_interval_excludes_zero=True,
            schema_version=SV,
        ).code
        == "IS6_INTERVAL_INCLUDES_ZERO"
    )
    assert is6_statistical_validity(
        includes_zero,
        min_sample_size=100,
        require_interval_excludes_zero=False,
        schema_version=SV,
    ).passed


def test_is7_requires_results_convergence_and_pairing():
    assert (
        is7_auction_sensitivity((), require_adaptive_pair=False, schema_version=SV).code
        == "IS7_RESULT_MISSING"
    )
    assert (
        is7_auction_sensitivity(
            (make_result(converged=False),),
            require_adaptive_pair=False,
            schema_version=SV,
        ).code
        == "IS7_NON_CONVERGENCE"
    )
    assert (
        is7_auction_sensitivity(
            (make_result(), make_result(scenario_hash="3" * 64)),
            require_adaptive_pair=False,
            schema_version=SV,
        ).code
        == "IS7_UNPAIRED_SCENARIOS"
    )
    assert (
        is7_auction_sensitivity(
            (make_result(), make_result(randomness_id="other")),
            require_adaptive_pair=False,
            schema_version=SV,
        ).code
        == "IS7_UNPAIRED_SCENARIOS"
    )


def test_is7_requires_both_adaptive_learners_and_no_sign_conflict():
    hedge = make_result(bidder_model=BidderModel.HEDGE)
    exp3 = make_result(bidder_model=BidderModel.EXP3_IX)
    fixed = make_result()
    assert (
        is7_auction_sensitivity((fixed,), require_adaptive_pair=True, schema_version=SV).code
        == "IS7_INCOMPLETE_LEARNER_PAIR"
    )
    assert (
        is7_auction_sensitivity((hedge,), require_adaptive_pair=False, schema_version=SV).code
        == "IS7_INCOMPLETE_LEARNER_PAIR"
    )
    assert is7_auction_sensitivity(
        (hedge, exp3), require_adaptive_pair=True, schema_version=SV
    ).passed
    conflict = make_result(bidder_model=BidderModel.EXP3_IX, revenue_delta=-0.1)
    assert (
        is7_auction_sensitivity(
            (hedge, conflict), require_adaptive_pair=True, schema_version=SV
        ).code
        == "IS7_ASSUMPTION_SIGN_CONFLICT"
    )
    assert is7_auction_sensitivity(
        (make_result(revenue_delta=0.0),),
        require_adaptive_pair=False,
        schema_version=SV,
    ).passed


def test_is8_blocks_early_test_and_allows_nonproduction_simulated_test():
    blocked = is8_evidence_action(
        evidence_class=EvidenceClass.UNIT_TESTED,
        proposed_action=NextAction.TEST,
        mode=DeploymentMode.FIXTURE,
        schema_version=SV,
    )
    assert blocked.code == "IS8_ACTION_EXCEEDS_EVIDENCE"
    assert blocked.coerce_to is NextAction.HOLD
    assert is8_evidence_action(
        evidence_class=EvidenceClass.SIMULATED,
        proposed_action=NextAction.TEST,
        mode=DeploymentMode.FIXTURE,
        schema_version=SV,
    ).passed
