"""Credential-free end-to-end orchestration for the ImagineSignal offline MVP.

This module has no production write port. It accepts only a replay client, frozen
aggregate outcomes, and an explicit synthetic auction scenario. The returned receipt
separates replay evidence from conditional simulation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock

from adjacency.imagine_signal.auction import (
    AuctionMechanism,
    AuctionScenario,
    AuctionSensitivityResult,
    LearningMode,
    run_auction_sensitivity,
)
from adjacency.imagine_signal.auction import (
    stable_hash as auction_stable_hash,
)
from adjacency.imagine_signal.canonical import canonical_payload, content_sha256
from adjacency.imagine_signal.contracts import (
    AssetState,
    AuctionSensitivityRecord,
    BidderModel,
    BrandSpec,
    CampaignSpec,
    ConvergenceRecord,
    CostStatus,
    CreativeAsset,
    DecisionReceipt,
    DeploymentMode,
    EvidenceClass,
    Mechanism,
    MutationSpec,
    NextAction,
    SignalDecision,
    SignalEstimate,
    SignalGateResult,
    UncertaintyInterval,
)
from adjacency.imagine_signal.decisions import build_signal_decision
from adjacency.imagine_signal.gates import (
    is0_request_budget,
    is1_lineage,
    is2_controlled_mutation,
    is3_provider_admission,
    is4_asset_integrity,
    is5_outcome_admission,
    is6_statistical_validity,
    is7_auction_sensitivity,
)
from adjacency.imagine_signal.imagine_client import FixtureImagineClient
from adjacency.imagine_signal.mutations import family_hash, validate_controlled_family
from adjacency.imagine_signal.outcomes import (
    InMemoryOutcomeRepository,
    estimate_ctr_difference,
    load_frozen_outcome_fixture,
)
from adjacency.imagine_signal.ports import (
    BudgetStatus,
    ImageGenerationRequest,
    ImagineMode,
    ProviderCallState,
    ResponseOrigin,
)
from adjacency.imagine_signal.ports import (
    CostStatus as AdapterCostStatus,
)
from adjacency.imagine_signal.receipts import build_decision_receipt


class OfflineServiceError(RuntimeError):
    """Fail-closed orchestration error with a stable local code."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True, slots=True)
class PlannedCreative:
    """One replay request bound to its intended lineage identity."""

    creative_id: str
    root_creative_id: str
    parent_creative_id: str | None
    mutation_id: str | None
    request: ImageGenerationRequest


@dataclass(frozen=True, slots=True)
class EfficiencyInput:
    """Frozen counts for one same-output-budget workflow."""

    generated_count: int
    qualified_count: int
    duplicate_paid_outputs: int
    quality_outputs: int
    qualified_quality_outputs: int
    lineage_complete_count: int
    total_cost_ticks: int

    def __post_init__(self) -> None:
        counts = (
            self.generated_count,
            self.qualified_count,
            self.duplicate_paid_outputs,
            self.quality_outputs,
            self.qualified_quality_outputs,
            self.lineage_complete_count,
            self.total_cost_ticks,
        )
        if any(isinstance(value, bool) or value < 0 for value in counts):
            raise ValueError("efficiency counts and cost must be non-negative integers")
        if self.qualified_count > self.generated_count:
            raise ValueError("qualified_count cannot exceed generated_count")
        if self.duplicate_paid_outputs > self.generated_count:
            raise ValueError("duplicate count cannot exceed generated_count")
        if self.quality_outputs > self.generated_count:
            raise ValueError("quality_outputs cannot exceed generated_count")
        if self.qualified_quality_outputs > self.quality_outputs:
            raise ValueError("qualified quality outputs cannot exceed quality outputs")
        if self.lineage_complete_count > self.generated_count:
            raise ValueError("lineage_complete_count cannot exceed generated_count")


@dataclass(frozen=True, slots=True)
class EfficiencyMetrics:
    """Recomputable workflow-efficiency metrics with unavailable denominators."""

    generated_count: int
    qualified_count: int
    duplicate_paid_outputs: int
    total_cost_ticks: int
    qualified_creative_yield: float | None
    cost_per_qualified_creative_ticks: float | None
    duplicate_paid_output_rate: float | None
    quality_precision: float | None
    lineage_completeness: float | None


@dataclass(frozen=True, slots=True)
class SameBudgetEfficiency:
    """Controlled workflow and an explicitly synthetic equal-budget baseline."""

    evidence_class: str
    cost_basis: str
    controlled: EfficiencyMetrics
    unstructured_baseline: EfficiencyMetrics


@dataclass(frozen=True, slots=True)
class OfflineFamilyRequest:
    """Complete immutable input to one credential-free family evaluation."""

    idempotency_key: str
    tenant_id: str
    expected_campaign_hash: str
    campaign: CampaignSpec
    brand: BrandSpec
    mutations: tuple[MutationSpec, ...]
    planned_creatives: tuple[PlannedCreative, ...]
    evaluation_control_creative_id: str
    evaluation_variant_creative_id: str
    expected_experiment_id: str
    arm_assignments: tuple[tuple[str, str], ...]
    observed_changes: tuple[tuple[str, tuple[str, ...]], ...]
    observed_locked_hashes: tuple[tuple[str, tuple[tuple[str, str], ...]], ...]
    outcome_fixture_path: str
    auction_scenario: AuctionScenario
    baseline_efficiency: EfficiencyInput
    proposed_action: NextAction
    now: datetime
    max_outcome_staleness: timedelta
    min_sample_size: int
    trace_id: str
    created_at: datetime

    def __post_init__(self) -> None:
        for field_name in (
            "idempotency_key",
            "tenant_id",
            "expected_experiment_id",
            "trace_id",
        ):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} must be nonempty")
        for field_name in ("now", "created_at"):
            value = getattr(self, field_name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{field_name} must include a UTC offset")
        if self.max_outcome_staleness < timedelta(0):
            raise ValueError("max_outcome_staleness cannot be negative")
        if self.min_sample_size < 0:
            raise ValueError("min_sample_size cannot be negative")


@dataclass(frozen=True, slots=True)
class OfflineRunResult:
    """Artifact-ready result of one complete replay evaluation."""

    request_hash: str
    assets: tuple[CreativeAsset, ...]
    signal_estimates: tuple[SignalEstimate, ...]
    auction_result: AuctionSensitivityResult
    auction_record: AuctionSensitivityRecord
    efficiency: SameBudgetEfficiency
    decision: SignalDecision
    receipt: DecisionReceipt
    explanation: str

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_version": 1,
            "request_hash": self.request_hash,
            "evidence_labels": {
                "assets": "FROZEN_REPLAY_SYNTHETIC_FIXTURE",
                "outcomes": "FROZEN_REPLAY_SYNTHETIC_AGGREGATES",
                "auction": "E2_SIMULATED",
            },
            "assets": [asset.model_dump(mode="json") for asset in self.assets],
            "signal_estimates": [
                estimate.model_dump(mode="json") for estimate in self.signal_estimates
            ],
            "auction_result": self.auction_result.to_dict(),
            "auction_receipt_record": self.auction_record.model_dump(mode="json"),
            "efficiency": canonical_payload(
                {
                    "evidence_class": self.efficiency.evidence_class,
                    "cost_basis": self.efficiency.cost_basis,
                    "controlled": _efficiency_dict(self.efficiency.controlled),
                    "unstructured_baseline": _efficiency_dict(
                        self.efficiency.unstructured_baseline
                    ),
                }
            ),
            "decision": self.decision.model_dump(mode="json"),
            "receipt": self.receipt.model_dump(mode="json"),
            "explanation": self.explanation,
            "prohibited_claims": [
                "The replay proves creative lift.",
                "The variant increases X revenue.",
                "ImagineSignal is authorized to publish, spend, or change ranking.",
            ],
        }


class InMemoryReceiptLedger:
    """Append-once local ledger used only by the offline service."""

    def __init__(self) -> None:
        self._receipts: dict[str, DecisionReceipt] = {}
        self._lock = Lock()

    def append_once(self, receipt: DecisionReceipt) -> DecisionReceipt:
        with self._lock:
            existing = self._receipts.get(receipt.receipt_id)
            if existing is None:
                self._receipts[receipt.receipt_id] = receipt
                return receipt
            if existing.receipt_sha256 == receipt.receipt_sha256:
                return existing
        raise OfflineServiceError(
            "SERVICE_RECEIPT_CONFLICT",
            "receipt_id was already committed with different content",
        )

    def get(self, receipt_id: str) -> DecisionReceipt | None:
        with self._lock:
            return self._receipts.get(receipt_id)


class OfflineImagineSignalService:
    """Idempotent fixture-only orchestrator with no live or write adapter."""

    def __init__(
        self,
        client: FixtureImagineClient,
        *,
        outcome_repository: InMemoryOutcomeRepository | None = None,
        receipt_ledger: InMemoryReceiptLedger | None = None,
    ) -> None:
        if client.mode is not ImagineMode.REPLAY:
            raise OfflineServiceError(
                "SERVICE_MODE_NOT_REPLAY",
                "the offline service accepts only a replay client",
            )
        self.client = client
        self.outcome_repository = outcome_repository or InMemoryOutcomeRepository()
        self.receipt_ledger = receipt_ledger or InMemoryReceiptLedger()
        self._completed: dict[str, tuple[str, OfflineRunResult]] = {}
        self._lock = Lock()

    def run(self, request: OfflineFamilyRequest) -> OfflineRunResult:
        """Execute exactly once per idempotency key and semantic request hash."""

        outcome_fixture = load_frozen_outcome_fixture(request.outcome_fixture_path)
        request_hash = _offline_request_hash(request, outcome_fixture.snapshots)
        with self._lock:
            previous = self._completed.get(request.idempotency_key)
            if previous is not None:
                previous_hash, previous_result = previous
                if previous_hash != request_hash:
                    raise OfflineServiceError(
                        "SERVICE_IDEMPOTENCY_CONFLICT",
                        "idempotency_key was reused with different semantic input",
                    )
                return previous_result
            result = self._execute(request, request_hash, outcome_fixture.snapshots)
            self._completed[request.idempotency_key] = (request_hash, result)
            return result

    def _execute(
        self,
        request: OfflineFamilyRequest,
        request_hash: str,
        snapshots,
    ) -> OfflineRunResult:
        _validate_request_contracts(request)
        assets, asset_gate_groups, total_cost_ticks = self._replay_assets(request)
        asset_by_id = {asset.creative_id: asset for asset in assets}

        for snapshot in snapshots:
            self.outcome_repository.append_once(snapshot)
        arm_by_creative = dict(request.arm_assignments)
        outcome_gates = tuple(
            is5_outcome_admission(
                snapshot,
                campaign=request.campaign,
                asset=_required_asset(asset_by_id, snapshot.creative_id),
                now=request.now,
                max_staleness=request.max_outcome_staleness,
                expected_experiment_id=request.expected_experiment_id,
                expected_arm_id=_required_arm(arm_by_creative, snapshot.creative_id),
                complete=True,
                schema_version="1",
            )
            for snapshot in snapshots
        )

        signal_estimates = _estimate_contexts(
            snapshots,
            control_creative_id=request.evaluation_control_creative_id,
            variant_creative_id=request.evaluation_variant_creative_id,
        )
        statistical_gates = tuple(
            is6_statistical_validity(
                estimate,
                min_sample_size=request.min_sample_size,
                require_interval_excludes_zero=False,
                schema_version="1",
            )
            for estimate in signal_estimates
        )

        runtime_auction = run_auction_sensitivity(request.auction_scenario)
        auction_record = _auction_record(runtime_auction)
        auction_gate = is7_auction_sensitivity(
            (auction_record,),
            require_adaptive_pair=False,
            schema_version="1",
        )

        mutation_gate = is2_controlled_mutation(
            request.mutations,
            observed_changes={key: value for key, value in request.observed_changes},
            observed_locked_hashes={
                key: dict(value) for key, value in request.observed_locked_hashes
            },
            schema_version="1",
        )
        budget_gate = is0_request_budget(
            mode=DeploymentMode.FIXTURE,
            allowed_modes=frozenset({DeploymentMode.FIXTURE}),
            requested_calls=len(request.planned_creatives),
            requested_images=len(assets),
            requested_quality_images=sum(
                "quality" in asset.provider_model_requested for asset in assets
            ),
            requested_cost_in_usd_ticks=total_cost_ticks,
            cost_status=CostStatus.EXACT,
            elapsed_ms=sum(asset.latency_ms for asset in assets),
            budget=request.campaign.generation_budget,
            generation_enabled=True,
            schema_version="1",
        )
        gate_results = (
            budget_gate,
            _aggregate_gate(asset_gate_groups["IS1"]),
            mutation_gate,
            _aggregate_gate(asset_gate_groups["IS3"]),
            _aggregate_gate(asset_gate_groups["IS4"]),
            _aggregate_gate(outcome_gates),
            _aggregate_gate(statistical_gates),
            auction_gate,
        )
        decision = build_signal_decision(
            schema_version="1",
            evidence_class=EvidenceClass.FROZEN_REPLAY,
            proposed_action=request.proposed_action,
            mode=DeploymentMode.FIXTURE,
            gate_results=gate_results,
            rationale=(
                "Synthetic replay may justify a non-production test proposal only. "
                "It cannot authorize publishing, spend, or ranking changes."
            ),
        )
        efficiency = _same_budget_efficiency(
            assets,
            gate_groups=asset_gate_groups,
            baseline=request.baseline_efficiency,
            total_cost_ticks=total_cost_ticks,
        )
        receipt_id = content_sha256(
            {"kind": "imagine_signal_receipt", "request_hash": request_hash}
        )
        receipt = build_decision_receipt(
            schema_version="1",
            receipt_id=receipt_id,
            receipt_version=1,
            tenant_id=request.tenant_id,
            campaign_hash=request.campaign.campaign_hash,
            family_hash=family_hash(request.mutations),
            asset_hashes=tuple(asset.asset_hash for asset in assets),
            outcome_hashes=tuple(snapshot.snapshot_hash for snapshot in snapshots),
            scenario_hashes=(runtime_auction.scenario_hash,),
            decision=decision,
            human_approval=None,
            cost_total_ticks=total_cost_ticks,
            cost_status=CostStatus.EXACT,
            trace_id=request.trace_id,
            created_at=request.created_at,
        )
        self.receipt_ledger.append_once(receipt)
        return OfflineRunResult(
            request_hash=request_hash,
            assets=assets,
            signal_estimates=signal_estimates,
            auction_result=runtime_auction,
            auction_record=auction_record,
            efficiency=efficiency,
            decision=decision,
            receipt=receipt,
            explanation=(
                "ImagineSignal replayed one approved control and two images that changed "
                "only the background tone. It joined clearly labeled synthetic totals, "
                "then tested how the small signal could matter in a made-up auction. "
                f"The allowed next step is {decision.final_action.value}. Nothing was "
                "published, no campaign money was spent, and no ranking was changed."
            ),
        )

    def _replay_assets(
        self,
        request: OfflineFamilyRequest,
    ) -> tuple[tuple[CreativeAsset, ...], dict[str, tuple[SignalGateResult, ...]], int]:
        assets: list[CreativeAsset] = []
        results_by_id = {}
        seen_media: dict[str, str] = {}
        duplicate_of: dict[str, str | None] = {}
        total_cost = 0
        for planned in request.planned_creatives:
            result = self.client.generate(planned.request)
            if (
                result.state is not ProviderCallState.COMPLETED
                or result.budget_status is not BudgetStatus.WITHIN_LIMIT
                or len(result.images) != 1
            ):
                raise OfflineServiceError(
                    "SERVICE_REPLAY_NOT_ADMITTED",
                    f"fixture for {planned.creative_id} is not one completed bounded image",
                )
            if (
                result.cost.status is not AdapterCostStatus.KNOWN
                or result.cost.ticks is None
                or result.response_origin is not ResponseOrigin.SYNTHETIC_FIXTURE
                or result.generator_id is None
                or result.provider_request_id is None
                or result.provider_model_resolved is None
                or result.moderation_respected is not True
                or result.latency_ms is None
            ):
                raise OfflineServiceError(
                    "SERVICE_REPLAY_METADATA_INCOMPLETE",
                    f"fixture metadata is incomplete for {planned.creative_id}",
                )
            image = result.images[0]
            previous = seen_media.get(image.media_sha256)
            duplicate_of[planned.creative_id] = previous
            seen_media.setdefault(image.media_sha256, planned.creative_id)
            state = AssetState.DUPLICATE if previous is not None else AssetState.VERIFIED
            asset = CreativeAsset(
                schema_version="1",
                tenant_id=request.tenant_id,
                campaign_id=request.campaign.campaign_id,
                creative_id=planned.creative_id,
                root_creative_id=planned.root_creative_id,
                parent_creative_id=planned.parent_creative_id,
                mutation_id=planned.mutation_id,
                request_hash=result.request_sha256,
                media_sha256=image.media_sha256,
                media_type=image.media_type,
                width=image.width,
                height=image.height,
                provider="synthetic_fixture",
                provider_model_requested=result.provider_model_requested,
                provider_model_resolved=result.provider_model_resolved,
                provider_request_id=result.provider_request_id,
                moderation_respected=True,
                cost_in_usd_ticks=result.cost.ticks,
                cost_status=CostStatus.EXACT,
                latency_ms=result.latency_ms,
                state=state,
            )
            assets.append(asset)
            results_by_id[asset.creative_id] = result
            total_cost += result.cost.ticks

        asset_by_id = {asset.creative_id: asset for asset in assets}
        lineage_results = tuple(
            is1_lineage(
                campaign=request.campaign,
                child=asset,
                parent=(
                    None
                    if asset.parent_creative_id is None
                    else asset_by_id.get(asset.parent_creative_id)
                ),
                schema_version="1",
            )
            for asset in assets
        )
        provider_results = tuple(
            is3_provider_admission(
                asset,
                provider_completed=(
                    results_by_id[asset.creative_id].state is ProviderCallState.COMPLETED
                ),
                schema_version="1",
            )
            for asset in assets
        )
        integrity_results = tuple(
            is4_asset_integrity(
                asset,
                computed_media_sha256=asset.media_sha256,
                actual_width=asset.width,
                actual_height=asset.height,
                duplicate_of=duplicate_of[asset.creative_id],
                schema_version="1",
            )
            for asset in assets
        )
        return (
            tuple(assets),
            {"IS1": lineage_results, "IS3": provider_results, "IS4": integrity_results},
            total_cost,
        )


def _validate_request_contracts(request: OfflineFamilyRequest) -> None:
    if (
        request.tenant_id != request.campaign.tenant_id
        or request.tenant_id != request.brand.tenant_id
    ):
        raise OfflineServiceError(
            "SERVICE_TENANT_MISMATCH",
            "request, campaign, and brand tenants must match",
        )
    if request.expected_campaign_hash != request.campaign.campaign_hash:
        raise OfflineServiceError(
            "SERVICE_STALE_CAMPAIGN",
            "expected_campaign_hash does not match the immutable campaign",
        )
    if request.campaign.brand_spec_hash != request.brand.brand_spec_hash:
        raise OfflineServiceError(
            "SERVICE_BRAND_HASH_MISMATCH",
            "campaign does not reference the supplied brand specification",
        )
    validation = validate_controlled_family(request.mutations)
    if not validation:
        raise OfflineServiceError(
            "SERVICE_MUTATION_FAMILY_INVALID",
            "; ".join(validation.details),
        )
    if not 2 <= len(request.mutations) <= 4:
        raise OfflineServiceError(
            "SERVICE_MUTATION_COUNT_INVALID",
            "the offline family requires two to four mutation levels",
        )
    planned_ids = tuple(item.creative_id for item in request.planned_creatives)
    if len(planned_ids) != len(set(planned_ids)):
        raise OfflineServiceError("SERVICE_CREATIVE_ID_DUPLICATE", "creative ids must be unique")
    if len(request.planned_creatives) != len(request.mutations) + 1:
        raise OfflineServiceError(
            "SERVICE_FAMILY_SIZE_MISMATCH",
            "planned creatives must contain one control plus every mutation",
        )
    roots = [item for item in request.planned_creatives if item.parent_creative_id is None]
    if len(roots) != 1 or roots[0].mutation_id is not None:
        raise OfflineServiceError(
            "SERVICE_ROOT_INVALID",
            "the family must contain exactly one unmutated root control",
        )
    mutation_by_id = {item.mutation_id: item for item in request.mutations}
    children = [item for item in request.planned_creatives if item.parent_creative_id is not None]
    if {item.mutation_id for item in children} != set(mutation_by_id):
        raise OfflineServiceError(
            "SERVICE_MUTATION_BINDING_MISMATCH",
            "each mutation must bind to exactly one planned child",
        )
    for item in request.planned_creatives:
        if item.request.n != 1:
            raise OfflineServiceError(
                "SERVICE_OUTPUT_COUNT_INVALID",
                "each controlled creative request must produce exactly one output",
            )
        if item.mutation_id is not None:
            mutation = mutation_by_id[item.mutation_id]
            expected_prompt_hash = content_sha256({"prompt": item.request.prompt})
            if mutation.prompt_hash != expected_prompt_hash:
                raise OfflineServiceError(
                    "SERVICE_PROMPT_HASH_MISMATCH",
                    f"request prompt does not match mutation {item.mutation_id}",
                )
    selected = {
        request.evaluation_control_creative_id,
        request.evaluation_variant_creative_id,
    }
    if len(selected) != 2 or not selected.issubset(planned_ids):
        raise OfflineServiceError(
            "SERVICE_EVALUATION_PAIR_INVALID",
            "evaluation control and variant must be distinct planned creatives",
        )
    assignments = dict(request.arm_assignments)
    if len(assignments) != len(request.arm_assignments) or not selected.issubset(assignments):
        raise OfflineServiceError(
            "SERVICE_ARM_ASSIGNMENT_INVALID",
            "arm assignments must be unique and include the evaluation pair",
        )
    if request.auction_scenario.learning_mode is not LearningMode.FIXED_BID:
        raise OfflineServiceError(
            "SERVICE_AUCTION_MODE_INVALID",
            "the receipt path uses fixed-bid sensitivity; adaptive modes are research-only",
        )


def _estimate_contexts(
    snapshots,
    *,
    control_creative_id: str,
    variant_creative_id: str,
) -> tuple[SignalEstimate, ...]:
    contexts = sorted({snapshot.context_id for snapshot in snapshots})
    estimates: list[SignalEstimate] = []
    for context_id in contexts:
        controls = [
            snapshot
            for snapshot in snapshots
            if snapshot.context_id == context_id and snapshot.creative_id == control_creative_id
        ]
        variants = [
            snapshot
            for snapshot in snapshots
            if snapshot.context_id == context_id and snapshot.creative_id == variant_creative_id
        ]
        if len(controls) != 1 or len(variants) != 1:
            raise OfflineServiceError(
                "SERVICE_OUTCOME_PAIR_MISSING",
                f"context {context_id!r} requires one control and one variant snapshot",
            )
        estimates.append(estimate_ctr_difference(controls[0], variants[0]))
    if not estimates:
        raise OfflineServiceError("SERVICE_OUTCOMES_MISSING", "no outcome contexts were found")
    return tuple(estimates)


def _auction_record(result: AuctionSensitivityResult) -> AuctionSensitivityRecord:
    mechanism = {
        AuctionMechanism.FIRST_PRICE: Mechanism.FIRST_PRICE,
        AuctionMechanism.SECOND_PRICE: Mechanism.SECOND_PRICE,
        AuctionMechanism.SOFT_FLOOR: Mechanism.SOFT_FLOOR,
    }[result.mechanism]
    bidder_model = {
        LearningMode.FIXED_BID: BidderModel.FIXED_BID,
        LearningMode.HEDGE_RESEARCH: BidderModel.HEDGE,
        LearningMode.EXP3_IX_RESEARCH: BidderModel.EXP3_IX,
    }[result.learning_mode]
    baseline_utility = result.baseline.total_advertiser_utility_per_impression
    variant_utility = result.variant.total_advertiser_utility_per_impression
    if baseline_utility is None or variant_utility is None:
        raise OfflineServiceError(
            "SERVICE_AUCTION_UTILITY_UNAVAILABLE",
            "receipt conversion requires declared advertiser values",
        )
    delta = result.delta.simulated_seller_revenue_per_impression
    standard_error = result.revenue_delta_standard_error or 0.0
    margin = 1.959963984540054 * standard_error
    fixed_bid = result.learning_mode is LearningMode.FIXED_BID
    convergence_values = (
        value
        for value in (
            result.baseline_convergence.max_total_variation,
            result.variant_convergence.max_total_variation,
        )
        if value is not None
    )
    stability_values = tuple(convergence_values)
    return AuctionSensitivityRecord(
        schema_version="1",
        scenario_hash=result.scenario_hash,
        baseline_signal_hash=result.baseline_evidence_hash,
        variant_signal_hash=result.variant_evidence_hash,
        common_randomness_id=result.common_randomness_id,
        mechanism=mechanism,
        bidder_model=bidder_model,
        boundary_crossing_rate=result.delta.focal_boundary_crossing_rate,
        allocation_change_rate=result.delta.allocation_change_rate,
        simulated_seller_revenue_baseline=(result.baseline.simulated_seller_revenue_per_impression),
        simulated_seller_revenue_variant=(result.variant.simulated_seller_revenue_per_impression),
        simulated_advertiser_utility_baseline=baseline_utility,
        simulated_advertiser_utility_variant=variant_utility,
        uncertainty=UncertaintyInterval(
            schema_version="1",
            low=delta - margin,
            high=delta + margin,
            method="paired_seed_normal_95" if result.repetitions > 1 else "single_seed_point",
        ),
        convergence_diagnostics=ConvergenceRecord(
            schema_version="1",
            converged=(
                True
                if fixed_bid
                else bool(
                    result.baseline_convergence.converged and result.variant_convergence.converged
                )
            ),
            iterations=result.repetitions * (result.horizon - result.burn_in),
            stability_metric=max(stability_values) if stability_values else None,
            notes=(
                result.baseline_convergence.status,
                result.variant_convergence.status,
            ),
        ),
    )


def _same_budget_efficiency(
    assets: tuple[CreativeAsset, ...],
    *,
    gate_groups: dict[str, tuple[SignalGateResult, ...]],
    baseline: EfficiencyInput,
    total_cost_ticks: int,
) -> SameBudgetEfficiency:
    if baseline.generated_count != len(assets):
        raise OfflineServiceError(
            "SERVICE_BASELINE_BUDGET_MISMATCH",
            "baseline and controlled workflows must use the same output count",
        )
    if baseline.total_cost_ticks != total_cost_ticks:
        raise OfflineServiceError(
            "SERVICE_BASELINE_COST_MISMATCH",
            "baseline and controlled workflows must use the same synthetic cost budget",
        )
    passed_by_asset = [
        all(group[index].passed for group in gate_groups.values()) for index in range(len(assets))
    ]
    controlled_input = EfficiencyInput(
        generated_count=len(assets),
        qualified_count=sum(passed_by_asset),
        duplicate_paid_outputs=sum(asset.state is AssetState.DUPLICATE for asset in assets),
        quality_outputs=sum("quality" in asset.provider_model_requested for asset in assets),
        qualified_quality_outputs=sum(
            passed and "quality" in asset.provider_model_requested
            for passed, asset in zip(passed_by_asset, assets, strict=True)
        ),
        lineage_complete_count=sum(
            asset.parent_creative_id is None
            or any(parent.creative_id == asset.parent_creative_id for parent in assets)
            for asset in assets
        ),
        total_cost_ticks=total_cost_ticks,
    )
    return SameBudgetEfficiency(
        evidence_class="SYNTHETIC_WORKFLOW_COMPARISON",
        cost_basis="synthetic_fixture_local_cost_ticks",
        controlled=_efficiency_metrics(controlled_input),
        unstructured_baseline=_efficiency_metrics(baseline),
    )


def _efficiency_metrics(value: EfficiencyInput) -> EfficiencyMetrics:
    return EfficiencyMetrics(
        generated_count=value.generated_count,
        qualified_count=value.qualified_count,
        duplicate_paid_outputs=value.duplicate_paid_outputs,
        total_cost_ticks=value.total_cost_ticks,
        qualified_creative_yield=_safe_ratio(value.qualified_count, value.generated_count),
        cost_per_qualified_creative_ticks=_safe_ratio(
            value.total_cost_ticks, value.qualified_count
        ),
        duplicate_paid_output_rate=_safe_ratio(value.duplicate_paid_outputs, value.generated_count),
        quality_precision=_safe_ratio(value.qualified_quality_outputs, value.quality_outputs),
        lineage_completeness=_safe_ratio(value.lineage_complete_count, value.generated_count),
    )


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _efficiency_dict(value: EfficiencyMetrics) -> dict[str, object]:
    return {
        "generated_count": value.generated_count,
        "qualified_count": value.qualified_count,
        "duplicate_paid_outputs": value.duplicate_paid_outputs,
        "total_cost_ticks": value.total_cost_ticks,
        "qualified_creative_yield": value.qualified_creative_yield,
        "cost_per_qualified_creative_ticks": value.cost_per_qualified_creative_ticks,
        "duplicate_paid_output_rate": value.duplicate_paid_output_rate,
        "quality_precision": value.quality_precision,
        "lineage_completeness": value.lineage_completeness,
    }


def _aggregate_gate(results: tuple[SignalGateResult, ...]) -> SignalGateResult:
    if not results:
        raise OfflineServiceError("SERVICE_GATE_INPUT_MISSING", "gate aggregation was empty")
    failures = [result for result in results if not result.passed]
    if not failures:
        return results[0]
    rank = {
        NextAction.TEST: 0,
        NextAction.EDIT: 1,
        NextAction.KEEP: 2,
        NextAction.HOLD: 3,
        NextAction.REVIEW: 4,
        NextAction.STOP: 5,
    }
    return max(failures, key=lambda item: rank[item.coerce_to or NextAction.HOLD])


def _required_asset(assets: dict[str, CreativeAsset], creative_id: str) -> CreativeAsset:
    try:
        return assets[creative_id]
    except KeyError as error:
        raise OfflineServiceError(
            "SERVICE_OUTCOME_ASSET_MISSING",
            f"outcome references unknown creative {creative_id!r}",
        ) from error


def _required_arm(assignments: dict[str, str], creative_id: str) -> str:
    try:
        return assignments[creative_id]
    except KeyError as error:
        raise OfflineServiceError(
            "SERVICE_OUTCOME_ARM_MISSING",
            f"no registered arm exists for creative {creative_id!r}",
        ) from error


def _offline_request_hash(request: OfflineFamilyRequest, snapshots) -> str:
    return content_sha256(
        {
            "idempotency_key": request.idempotency_key,
            "tenant_id": request.tenant_id,
            "expected_campaign_hash": request.expected_campaign_hash,
            "campaign_hash": request.campaign.campaign_hash,
            "brand_hash": request.brand.brand_spec_hash,
            "mutation_hashes": [item.mutation_hash for item in request.mutations],
            "planned_creatives": [
                {
                    "creative_id": item.creative_id,
                    "root_creative_id": item.root_creative_id,
                    "parent_creative_id": item.parent_creative_id,
                    "mutation_id": item.mutation_id,
                    "request": item.request,
                }
                for item in request.planned_creatives
            ],
            "evaluation_pair": [
                request.evaluation_control_creative_id,
                request.evaluation_variant_creative_id,
            ],
            "expected_experiment_id": request.expected_experiment_id,
            "arm_assignments": request.arm_assignments,
            "observed_changes": request.observed_changes,
            "observed_locked_hashes": request.observed_locked_hashes,
            "outcome_hashes": sorted(snapshot.snapshot_hash for snapshot in snapshots),
            "auction_scenario_hash": auction_stable_hash(request.auction_scenario),
            "baseline_efficiency": {
                "generated_count": request.baseline_efficiency.generated_count,
                "qualified_count": request.baseline_efficiency.qualified_count,
                "duplicate_paid_outputs": request.baseline_efficiency.duplicate_paid_outputs,
                "quality_outputs": request.baseline_efficiency.quality_outputs,
                "qualified_quality_outputs": (
                    request.baseline_efficiency.qualified_quality_outputs
                ),
                "lineage_complete_count": (request.baseline_efficiency.lineage_complete_count),
                "total_cost_ticks": request.baseline_efficiency.total_cost_ticks,
            },
            "proposed_action": request.proposed_action,
            "now": request.now,
            "max_outcome_staleness_seconds": request.max_outcome_staleness.total_seconds(),
            "min_sample_size": request.min_sample_size,
            "trace_id": request.trace_id,
            "created_at": request.created_at,
        }
    )


__all__ = [
    "EfficiencyInput",
    "EfficiencyMetrics",
    "InMemoryReceiptLedger",
    "OfflineFamilyRequest",
    "OfflineImagineSignalService",
    "OfflineRunResult",
    "OfflineServiceError",
    "PlannedCreative",
    "SameBudgetEfficiency",
]
