"""Pure IS0 through IS8 gates for creative lineage and evidence admission."""

from __future__ import annotations

import hmac
from collections.abc import Collection, Mapping, Sequence
from datetime import datetime, timedelta

from adjacency.imagine_signal.contracts import (
    AssetState,
    AuctionSensitivityRecord,
    BidderModel,
    CampaignSpec,
    CostStatus,
    CreativeAsset,
    DeploymentMode,
    EvidenceClass,
    GenerationBudget,
    MutationSpec,
    NextAction,
    OutcomeSnapshot,
    SignalEstimate,
    SignalGateResult,
)
from adjacency.imagine_signal.decisions import evidence_capped_action
from adjacency.imagine_signal.mutations import validate_controlled_family


def _ok(gate: str, schema_version: str) -> SignalGateResult:
    return SignalGateResult(
        schema_version=schema_version,
        gate=gate,
        passed=True,
        code=f"{gate}_OK",
    )


def _fail(
    gate: str,
    code: str,
    detail: str,
    coerce_to: NextAction,
    schema_version: str,
    *,
    security_signal: bool = False,
) -> SignalGateResult:
    return SignalGateResult(
        schema_version=schema_version,
        gate=gate,
        passed=False,
        code=code,
        detail=detail,
        coerce_to=coerce_to,
        security_signal=security_signal,
    )


def is0_request_budget(
    *,
    mode: DeploymentMode,
    allowed_modes: frozenset[DeploymentMode],
    requested_calls: int,
    requested_images: int,
    requested_quality_images: int,
    requested_cost_in_usd_ticks: int | None,
    cost_status: CostStatus,
    elapsed_ms: int,
    budget: GenerationBudget,
    generation_enabled: bool,
    schema_version: str,
) -> SignalGateResult:
    """Admit only an explicit mode and work request bounded in every dimension."""

    gate = "IS0"
    numeric = (requested_calls, requested_images, requested_quality_images, elapsed_ms)
    if any(value < 0 for value in numeric) or (
        requested_cost_in_usd_ticks is not None and requested_cost_in_usd_ticks < 0
    ):
        return _fail(
            gate,
            "IS0_REQUEST_INVALID",
            "requested work and elapsed values must be non-negative",
            NextAction.STOP,
            schema_version,
        )
    if not generation_enabled:
        return _fail(
            gate,
            "IS0_GENERATION_DISABLED",
            "the generation kill switch is disabled",
            NextAction.HOLD,
            schema_version,
        )
    if not isinstance(mode, DeploymentMode) or mode not in allowed_modes:
        return _fail(
            gate,
            "IS0_MODE_NOT_ALLOWED",
            f"deployment mode {getattr(mode, 'value', mode)!r} is not admitted for this request",
            NextAction.STOP,
            schema_version,
            security_signal=True,
        )
    if requested_quality_images > requested_images:
        return _fail(
            gate,
            "IS0_REQUEST_INVALID",
            "quality image count cannot exceed total image count",
            NextAction.STOP,
            schema_version,
        )
    if cost_status is CostStatus.UNKNOWN or requested_cost_in_usd_ticks is None:
        return _fail(
            gate,
            "IS0_COST_UNKNOWN",
            "unknown cost cannot be admitted as zero",
            NextAction.HOLD,
            schema_version,
        )
    breaches: list[str] = []
    if requested_calls > budget.max_calls:
        breaches.append("calls")
    if requested_images > budget.max_images:
        breaches.append("images")
    if requested_quality_images > budget.max_quality_images:
        breaches.append("quality images")
    if requested_cost_in_usd_ticks > budget.max_cost_in_usd_ticks:
        breaches.append("cost")
    if elapsed_ms > budget.max_wallclock_ms:
        breaches.append("wallclock")
    if breaches:
        return _fail(
            gate,
            "IS0_BUDGET_EXCEEDED",
            f"request exceeds budget for: {', '.join(breaches)}",
            NextAction.STOP,
            schema_version,
        )
    return _ok(gate, schema_version)


def is1_lineage(
    *,
    campaign: CampaignSpec,
    child: CreativeAsset,
    parent: CreativeAsset | None,
    schema_version: str,
) -> SignalGateResult:
    """Validate campaign, tenant, parent, and root lineage."""

    gate = "IS1"
    if child.tenant_id != campaign.tenant_id:
        return _fail(
            gate,
            "IS1_CAMPAIGN_TENANT_MISMATCH",
            "the creative tenant does not match the campaign tenant",
            NextAction.STOP,
            schema_version,
            security_signal=True,
        )
    if child.campaign_id != campaign.campaign_id:
        return _fail(
            gate,
            "IS1_CAMPAIGN_MISMATCH",
            "the creative campaign does not match the admitted campaign",
            NextAction.STOP,
            schema_version,
        )
    is_root = child.creative_id == child.root_creative_id
    if is_root:
        if parent is not None:
            return _fail(
                gate,
                "IS1_ROOT_HAS_PARENT",
                "a root creative cannot resolve to a parent",
                NextAction.STOP,
                schema_version,
            )
        return _ok(gate, schema_version)
    if parent is None:
        return _fail(
            gate,
            "IS1_PARENT_MISSING",
            f"parent {child.parent_creative_id!r} was not found",
            NextAction.STOP,
            schema_version,
        )
    if parent.tenant_id != child.tenant_id:
        return _fail(
            gate,
            "IS1_PARENT_TENANT_MISMATCH",
            "parent and child belong to different tenants",
            NextAction.STOP,
            schema_version,
            security_signal=True,
        )
    if parent.campaign_id != child.campaign_id:
        return _fail(
            gate,
            "IS1_PARENT_CAMPAIGN_MISMATCH",
            "parent and child belong to different campaigns",
            NextAction.STOP,
            schema_version,
        )
    if parent.creative_id != child.parent_creative_id:
        return _fail(
            gate,
            "IS1_PARENT_ID_MISMATCH",
            "resolved parent does not match parent_creative_id",
            NextAction.STOP,
            schema_version,
        )
    if parent.root_creative_id != child.root_creative_id:
        return _fail(
            gate,
            "IS1_ROOT_MISMATCH",
            "parent and child do not share the same root creative",
            NextAction.STOP,
            schema_version,
        )
    return _ok(gate, schema_version)


def is2_controlled_mutation(
    mutations: Sequence[MutationSpec],
    *,
    observed_changes: Mapping[str, Collection[str]] | None,
    observed_locked_hashes: Mapping[str, Mapping[str, str]] | None,
    schema_version: str,
) -> SignalGateResult:
    """Admit only a coherent family whose outputs changed one declared atom."""

    validation = validate_controlled_family(
        mutations,
        observed_changes=observed_changes,
        observed_locked_hashes=observed_locked_hashes,
    )
    if not validation:
        return _fail(
            "IS2",
            "IS2_UNCONTROLLED_MUTATION",
            "; ".join(validation.details),
            NextAction.REVIEW,
            schema_version,
        )
    return _ok("IS2", schema_version)


def is3_provider_admission(
    asset: CreativeAsset,
    *,
    provider_completed: bool,
    schema_version: str,
) -> SignalGateResult:
    """Reject ambiguous completion, moderation bypass, and unknown paid cost."""

    gate = "IS3"
    if not provider_completed or asset.state is AssetState.PLANNED:
        return _fail(
            gate,
            "IS3_PROVIDER_INCOMPLETE",
            "provider completion is absent or ambiguous",
            NextAction.HOLD,
            schema_version,
        )
    if asset.state is AssetState.MODERATION_REJECTED:
        return _fail(
            gate,
            "IS3_MODERATION_REJECTED",
            "the provider rejected this output under moderation",
            NextAction.STOP,
            schema_version,
        )
    if not asset.moderation_respected:
        return _fail(
            gate,
            "IS3_MODERATION_BYPASS",
            "provider moderation was not respected",
            NextAction.STOP,
            schema_version,
            security_signal=True,
        )
    if asset.state is AssetState.QUARANTINED:
        return _fail(
            gate,
            "IS3_RESPONSE_QUARANTINED",
            "the normalized provider response was quarantined",
            NextAction.STOP,
            schema_version,
        )
    if asset.cost_status is CostStatus.UNKNOWN or asset.cost_in_usd_ticks is None:
        return _fail(
            gate,
            "IS3_COST_UNKNOWN",
            "provider cost is unknown and cannot be treated as zero",
            NextAction.HOLD,
            schema_version,
        )
    return _ok(gate, schema_version)


def is4_asset_integrity(
    asset: CreativeAsset,
    *,
    computed_media_sha256: str,
    actual_width: int,
    actual_height: int,
    duplicate_of: str | None,
    schema_version: str,
) -> SignalGateResult:
    """Admit only persisted bytes with the declared digest and dimensions."""

    gate = "IS4"
    if len(computed_media_sha256) != 64 or any(
        char not in "0123456789abcdef" for char in computed_media_sha256
    ):
        return _fail(
            gate,
            "IS4_COMPUTED_HASH_INVALID",
            "computed media digest is not lower-case SHA-256",
            NextAction.STOP,
            schema_version,
        )
    if actual_width <= 0 or actual_height <= 0:
        return _fail(
            gate,
            "IS4_MEDIA_SHAPE_INVALID",
            "actual media dimensions must be positive",
            NextAction.STOP,
            schema_version,
        )
    if not hmac.compare_digest(asset.media_sha256, computed_media_sha256):
        return _fail(
            gate,
            "IS4_ASSET_HASH_MISMATCH",
            "persisted media bytes do not match media_sha256",
            NextAction.STOP,
            schema_version,
        )
    if (asset.width, asset.height) != (actual_width, actual_height):
        return _fail(
            gate,
            "IS4_DIMENSION_MISMATCH",
            (
                f"asset declares {asset.width}x{asset.height}, actual media is "
                f"{actual_width}x{actual_height}"
            ),
            NextAction.STOP,
            schema_version,
        )
    if duplicate_of is not None or asset.state is AssetState.DUPLICATE:
        return _fail(
            gate,
            "IS4_EXACT_DUPLICATE",
            f"asset duplicates {duplicate_of or 'a previously admitted asset'}",
            NextAction.KEEP,
            schema_version,
        )
    if asset.state is not AssetState.VERIFIED:
        return _fail(
            gate,
            "IS4_ASSET_NOT_VERIFIED",
            f"asset state {asset.state.value} is not admissible",
            NextAction.HOLD,
            schema_version,
        )
    return _ok(gate, schema_version)


def is5_outcome_admission(
    snapshot: OutcomeSnapshot,
    *,
    campaign: CampaignSpec,
    asset: CreativeAsset,
    now: datetime,
    max_staleness: timedelta,
    expected_experiment_id: str,
    expected_arm_id: str,
    complete: bool,
    schema_version: str,
) -> SignalGateResult:
    """Validate aggregate outcome identity, window, freshness, and completeness."""

    gate = "IS5"
    if now.tzinfo is None or now.utcoffset() is None or max_staleness < timedelta(0):
        return _fail(
            gate,
            "IS5_VALIDATION_CONFIG_INVALID",
            "now must be timezone-aware and max_staleness non-negative",
            NextAction.HOLD,
            schema_version,
        )
    if not complete:
        return _fail(
            gate,
            "IS5_OUTCOME_INCOMPLETE",
            "the aggregate outcome snapshot is partial",
            NextAction.HOLD,
            schema_version,
        )
    if snapshot.tenant_id != campaign.tenant_id or snapshot.tenant_id != asset.tenant_id:
        return _fail(
            gate,
            "IS5_OUTCOME_TENANT_MISMATCH",
            "outcome, campaign, and asset tenants do not match",
            NextAction.STOP,
            schema_version,
            security_signal=True,
        )
    if snapshot.campaign_id != campaign.campaign_id or snapshot.campaign_id != asset.campaign_id:
        return _fail(
            gate,
            "IS5_OUTCOME_CAMPAIGN_MISMATCH",
            "outcome, campaign, and asset campaign ids do not match",
            NextAction.HOLD,
            schema_version,
        )
    if snapshot.creative_id != asset.creative_id:
        return _fail(
            gate,
            "IS5_OUTCOME_CREATIVE_MISMATCH",
            "outcome creative id does not match the joined asset",
            NextAction.HOLD,
            schema_version,
        )
    if snapshot.experiment_id != expected_experiment_id or snapshot.arm_id != expected_arm_id:
        return _fail(
            gate,
            "IS5_EXPERIMENT_ARM_MISMATCH",
            "outcome experiment or arm does not match the expected assignment",
            NextAction.HOLD,
            schema_version,
        )
    window = campaign.measurement_window
    if snapshot.measurement_start < window.start or snapshot.measurement_end > window.end:
        return _fail(
            gate,
            "IS5_OUTCOME_WINDOW_MISMATCH",
            "outcome measurement window falls outside the campaign window",
            NextAction.HOLD,
            schema_version,
        )
    if snapshot.observed_at > now:
        return _fail(
            gate,
            "IS5_OUTCOME_FROM_FUTURE",
            "outcome observed_at is later than the supplied clock",
            NextAction.HOLD,
            schema_version,
        )
    if now - snapshot.observed_at > max_staleness:
        return _fail(
            gate,
            "IS5_OUTCOME_STALE",
            "outcome snapshot is older than the admitted freshness window",
            NextAction.HOLD,
            schema_version,
        )
    return _ok(gate, schema_version)


def is6_statistical_validity(
    estimate: SignalEstimate,
    *,
    min_sample_size: int,
    require_interval_excludes_zero: bool,
    schema_version: str,
) -> SignalGateResult:
    """Validate metric namespace, sample size, and optional interval criterion."""

    gate = "IS6"
    if min_sample_size < 0:
        return _fail(
            gate,
            "IS6_THRESHOLD_INVALID",
            "min_sample_size must be non-negative",
            NextAction.HOLD,
            schema_version,
        )
    namespaces = ("observed.", "predicted.", "simulated.")
    if not estimate.metric.startswith(namespaces):
        return _fail(
            gate,
            "IS6_METRIC_NAMESPACE_INVALID",
            "metric must declare observed, predicted, or simulated provenance",
            NextAction.HOLD,
            schema_version,
        )
    if estimate.sample_size < min_sample_size:
        return _fail(
            gate,
            "IS6_INSUFFICIENT_EVIDENCE",
            f"sample size {estimate.sample_size} is below {min_sample_size}",
            NextAction.HOLD,
            schema_version,
        )
    if require_interval_excludes_zero and estimate.interval_low <= 0.0 <= estimate.interval_high:
        return _fail(
            gate,
            "IS6_INTERVAL_INCLUDES_ZERO",
            "the predeclared uncertainty interval includes zero",
            NextAction.HOLD,
            schema_version,
        )
    return _ok(gate, schema_version)


def _sign(value: float, tolerance: float = 1e-12) -> int:
    if value > tolerance:
        return 1
    if value < -tolerance:
        return -1
    return 0


def is7_auction_sensitivity(
    results: Sequence[AuctionSensitivityRecord],
    *,
    require_adaptive_pair: bool,
    schema_version: str,
) -> SignalGateResult:
    """Require paired, converged, non-cherry-picked sensitivity evidence."""

    gate = "IS7"
    if not results:
        return _fail(
            gate,
            "IS7_RESULT_MISSING",
            "no auction sensitivity result was supplied",
            NextAction.HOLD,
            schema_version,
        )
    if any(not result.convergence_diagnostics.converged for result in results):
        return _fail(
            gate,
            "IS7_NON_CONVERGENCE",
            "at least one configured learner did not converge",
            NextAction.REVIEW,
            schema_version,
        )
    scenario_hashes = {result.scenario_hash for result in results}
    randomness_ids = {result.common_randomness_id for result in results}
    if len(scenario_hashes) != 1 or len(randomness_ids) != 1:
        return _fail(
            gate,
            "IS7_UNPAIRED_SCENARIOS",
            "results must share one scenario and common-randomness identifier",
            NextAction.REVIEW,
            schema_version,
        )
    models = {result.bidder_model for result in results}
    adaptive = {BidderModel.HEDGE, BidderModel.EXP3_IX}
    if require_adaptive_pair and not adaptive.issubset(models):
        return _fail(
            gate,
            "IS7_INCOMPLETE_LEARNER_PAIR",
            "Hedge and EXP3-IX must be reported together",
            NextAction.REVIEW,
            schema_version,
        )
    if models & adaptive and not adaptive.issubset(models):
        return _fail(
            gate,
            "IS7_INCOMPLETE_LEARNER_PAIR",
            "one adaptive learner result was omitted",
            NextAction.REVIEW,
            schema_version,
        )
    signs = {
        _sign(result.simulated_seller_revenue_variant - result.simulated_seller_revenue_baseline)
        for result in results
    }
    if 1 in signs and -1 in signs:
        return _fail(
            gate,
            "IS7_ASSUMPTION_SIGN_CONFLICT",
            "simulated seller-revenue direction changes across assumptions",
            NextAction.REVIEW,
            schema_version,
        )
    return _ok(gate, schema_version)


def is8_evidence_action(
    *,
    evidence_class: EvidenceClass,
    proposed_action: NextAction,
    mode: DeploymentMode,
    schema_version: str,
) -> SignalGateResult:
    """Enforce the total evidence-to-action ceiling."""

    admitted = evidence_capped_action(proposed_action, evidence_class, mode)
    if admitted is proposed_action:
        return _ok("IS8", schema_version)
    return _fail(
        "IS8",
        "IS8_ACTION_EXCEEDS_EVIDENCE",
        (
            f"{proposed_action.value} is not admitted for {evidence_class.value} "
            f"evidence in {mode.value} mode"
        ),
        admitted,
        schema_version,
    )
