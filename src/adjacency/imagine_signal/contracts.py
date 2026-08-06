"""Immutable, versioned contracts for the ImagineSignal bounded context."""

from __future__ import annotations

import math
import re
from datetime import datetime
from enum import Enum, StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from adjacency.imagine_signal.canonical import content_sha256, normalize_text

SHA256_PATTERN = r"^[0-9a-f]{64}$"
GATE_PATTERN = r"^IS[0-8]$"
GATE_CODE_PATTERN = r"^IS[0-8]_[A-Z0-9_]+$"


class EvidenceClass(StrEnum):
    """The provenance class that limits actions and claims."""

    PROPOSED = "PROPOSED"
    IMPLEMENTED = "IMPLEMENTED"
    UNIT_TESTED = "UNIT_TESTED"
    FROZEN_REPLAY = "FROZEN_REPLAY"
    SIMULATED = "SIMULATED"
    SHADOW_ESTIMATE = "SHADOW_ESTIMATE"
    RANDOMIZED_DISPLAY_ONLY = "RANDOMIZED_DISPLAY_ONLY"
    RANDOMIZED_END_TO_END = "RANDOMIZED_END_TO_END"
    SCALED_PRODUCTION = "SCALED_PRODUCTION"


class NextAction(StrEnum):
    """MVP actions. None of these writes to an ads system."""

    KEEP = "KEEP"
    EDIT = "EDIT"
    TEST = "TEST"
    HOLD = "HOLD"
    REVIEW = "REVIEW"
    STOP = "STOP"


class DataOrigin(StrEnum):
    SYNTHETIC = "SYNTHETIC"
    FROZEN_REPLAY = "FROZEN_REPLAY"
    SHADOW_LOG = "SHADOW_LOG"
    RANDOMIZED_EXPERIMENT = "RANDOMIZED_EXPERIMENT"
    PRODUCTION = "PRODUCTION"


class AssetState(StrEnum):
    PLANNED = "PLANNED"
    GENERATED = "GENERATED"
    MODERATION_REJECTED = "MODERATION_REJECTED"
    VERIFIED = "VERIFIED"
    DUPLICATE = "DUPLICATE"
    QUARANTINED = "QUARANTINED"


class Mechanism(StrEnum):
    FIRST_PRICE = "FIRST_PRICE"
    SECOND_PRICE = "SECOND_PRICE"
    SOFT_FLOOR = "SOFT_FLOOR"


class BidderModel(StrEnum):
    FIXED_BID = "FIXED_BID"
    HEDGE = "HEDGE"
    EXP3_IX = "EXP3_IX"


class DeploymentMode(StrEnum):
    FIXTURE = "fixture"
    RECORD = "record"
    SHADOW = "shadow"
    DRAFT_BETA = "draft_beta"
    EXPERIMENT_DISPLAY_ONLY = "experiment_display_only"
    EXPERIMENT_SIGNAL_AWARE = "experiment_signal_aware"


class CostStatus(StrEnum):
    EXACT = "EXACT"
    ESTIMATED = "ESTIMATED"
    UNKNOWN = "UNKNOWN"


def _normalize_strings(value: object) -> object:
    if isinstance(value, Enum):
        return value
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, tuple):
        return tuple(_normalize_strings(item) for item in value)
    if isinstance(value, list):
        return [_normalize_strings(item) for item in value]
    if isinstance(value, dict):
        return {
            normalize_text(key) if isinstance(key, str) else key: _normalize_strings(item)
            for key, item in value.items()
        }
    return value


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a UTC offset")


def _require_unique(values: tuple[str, ...], field_name: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must not contain duplicates")


class SignalContract(BaseModel):
    """Base contract: immutable, strict, versioned, and closed to unknown fields."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
        validate_default=True,
    )

    schema_version: str = Field(min_length=1)

    @field_validator("*", mode="before")
    @classmethod
    def _nfc_normalize_strings(cls, value: object) -> object:
        return _normalize_strings(value)

    @property
    def content_hash(self) -> str:
        return content_sha256(self.model_dump(mode="json"))


class GenerationBudget(SignalContract):
    max_calls: int = Field(ge=0)
    max_images: int = Field(ge=0)
    max_quality_images: int = Field(ge=0)
    max_cost_in_usd_ticks: int = Field(ge=0)
    max_wallclock_ms: int = Field(gt=0)

    @model_validator(mode="after")
    def _quality_is_within_total(self) -> Self:
        if self.max_quality_images > self.max_images:
            raise ValueError("max_quality_images cannot exceed max_images")
        return self


class MeasurementWindow(SignalContract):
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def _ordered_and_aware(self) -> Self:
        _require_aware(self.start, "start")
        _require_aware(self.end, "end")
        if self.end <= self.start:
            raise ValueError("measurement window end must be after start")
        return self


class CampaignSpec(SignalContract):
    tenant_id: str = Field(min_length=1)
    campaign_id: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    audience_contexts: tuple[str, ...] = Field(min_length=1)
    measurement_metric: str = Field(min_length=1)
    measurement_window: MeasurementWindow
    brand_spec_hash: str = Field(pattern=SHA256_PATTERN)
    generation_budget: GenerationBudget
    created_by: str = Field(min_length=1)

    @model_validator(mode="after")
    def _contexts_are_unique(self) -> Self:
        _require_unique(self.audience_contexts, "audience_contexts")
        return self

    @property
    def campaign_hash(self) -> str:
        return self.content_hash


class BrandSpec(SignalContract):
    tenant_id: str = Field(min_length=1)
    brand_spec_id: str = Field(min_length=1)
    required_elements: tuple[str, ...] = ()
    prohibited_elements: tuple[str, ...] = ()
    locked_text_claims: tuple[str, ...] = ()
    locked_product_identity: tuple[str, ...] = ()
    logo_constraints: tuple[str, ...] = ()
    source_provenance: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _sets_are_unique(self) -> Self:
        for field_name in (
            "required_elements",
            "prohibited_elements",
            "locked_text_claims",
            "locked_product_identity",
            "logo_constraints",
            "source_provenance",
        ):
            _require_unique(getattr(self, field_name), field_name)
        overlap = set(self.required_elements) & set(self.prohibited_elements)
        if overlap:
            raise ValueError(f"elements cannot be both required and prohibited: {sorted(overlap)}")
        return self

    @property
    def brand_spec_hash(self) -> str:
        return self.content_hash


class LockedAttribute(SignalContract):
    name: str = Field(min_length=1)
    value_sha256: str = Field(pattern=SHA256_PATTERN)


class MutationSpec(SignalContract):
    tenant_id: str = Field(min_length=1)
    mutation_id: str = Field(min_length=1)
    family_id: str = Field(min_length=1)
    campaign_id: str = Field(min_length=1)
    root_asset_id: str = Field(min_length=1)
    parent_asset_id: str = Field(min_length=1)
    axis: str = Field(min_length=1)
    level: str = Field(min_length=1)
    locked_attributes: tuple[LockedAttribute, ...] = ()
    prompt_template_version: str = Field(min_length=1)
    prompt_hash: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _locked_attributes_are_unique(self) -> Self:
        names = tuple(item.name for item in self.locked_attributes)
        _require_unique(names, "locked_attributes names")
        if self.axis in names:
            raise ValueError("the mutable axis cannot also be a locked attribute")
        return self

    @property
    def mutation_hash(self) -> str:
        return self.content_hash


class CreativeAsset(SignalContract):
    tenant_id: str = Field(min_length=1)
    campaign_id: str = Field(min_length=1)
    creative_id: str = Field(min_length=1)
    root_creative_id: str = Field(min_length=1)
    parent_creative_id: str | None = Field(default=None, min_length=1)
    mutation_id: str | None = Field(default=None, min_length=1)
    request_hash: str = Field(pattern=SHA256_PATTERN)
    media_sha256: str = Field(pattern=SHA256_PATTERN)
    media_type: Literal["image/png", "image/jpeg"]
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    provider: str = Field(min_length=1)
    provider_model_requested: str = Field(min_length=1)
    provider_model_resolved: str = Field(min_length=1)
    provider_request_id: str = Field(min_length=1)
    moderation_respected: bool
    cost_in_usd_ticks: int | None = Field(default=None, ge=0)
    cost_status: CostStatus
    latency_ms: int = Field(ge=0)
    state: AssetState

    @model_validator(mode="after")
    def _lineage_and_cost_are_coherent(self) -> Self:
        is_root = self.creative_id == self.root_creative_id
        if is_root and self.parent_creative_id is not None:
            raise ValueError("a root creative cannot have a parent")
        if not is_root and self.parent_creative_id is None:
            raise ValueError("a non-root creative requires a parent")
        if self.parent_creative_id == self.creative_id:
            raise ValueError("a creative cannot be its own parent")
        if is_root and self.mutation_id is not None:
            raise ValueError("a root creative cannot carry a mutation_id")
        if not is_root and self.mutation_id is None:
            raise ValueError("a non-root creative requires a mutation_id")
        if self.cost_status is CostStatus.UNKNOWN and self.cost_in_usd_ticks is not None:
            raise ValueError("unknown cost must use a null cost_in_usd_ticks")
        if self.cost_status is not CostStatus.UNKNOWN and self.cost_in_usd_ticks is None:
            raise ValueError("known or estimated cost requires cost_in_usd_ticks")
        return self

    @property
    def asset_hash(self) -> str:
        return self.content_hash


class OutcomeSnapshot(SignalContract):
    tenant_id: str = Field(min_length=1)
    campaign_id: str = Field(min_length=1)
    creative_id: str = Field(min_length=1)
    context_id: str = Field(min_length=1)
    experiment_id: str = Field(min_length=1)
    arm_id: str = Field(min_length=1)
    origin: DataOrigin
    measurement_start: datetime
    measurement_end: datetime
    attribution_method: str = Field(min_length=1)
    impressions: int = Field(ge=0)
    clicks: int = Field(ge=0)
    conversions: int | None = Field(default=None, ge=0)
    advertiser_spend_ticks: int | None = Field(default=None, ge=0)
    attributed_purchase_value_ticks: int | None = Field(default=None, ge=0)
    source_snapshot_id: str = Field(min_length=1)
    source_sha256: str = Field(pattern=SHA256_PATTERN)
    observed_at: datetime

    @model_validator(mode="after")
    def _counts_and_window_are_coherent(self) -> Self:
        _require_aware(self.measurement_start, "measurement_start")
        _require_aware(self.measurement_end, "measurement_end")
        _require_aware(self.observed_at, "observed_at")
        if self.measurement_end <= self.measurement_start:
            raise ValueError("measurement_end must be after measurement_start")
        if self.observed_at < self.measurement_end:
            raise ValueError("observed_at cannot precede measurement_end")
        if self.clicks > self.impressions:
            raise ValueError("clicks cannot exceed impressions")
        if self.conversions is not None and self.conversions > self.impressions:
            raise ValueError("conversions cannot exceed impressions")
        return self

    @property
    def snapshot_hash(self) -> str:
        return self.content_hash


class SignalEstimate(SignalContract):
    baseline_creative_id: str = Field(min_length=1)
    variant_creative_id: str = Field(min_length=1)
    context_id: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    baseline_estimate: float
    variant_estimate: float
    absolute_delta: float
    relative_delta: float | None = None
    interval_low: float
    interval_high: float
    method: str = Field(min_length=1)
    sample_size: int = Field(ge=0)
    evidence_class: EvidenceClass
    outcome_snapshot_hashes: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _estimate_is_coherent(self) -> Self:
        numbers = (
            self.baseline_estimate,
            self.variant_estimate,
            self.absolute_delta,
            self.interval_low,
            self.interval_high,
        )
        if self.relative_delta is not None:
            numbers += (self.relative_delta,)
        if not all(math.isfinite(value) for value in numbers):
            raise ValueError("signal estimates must be finite")
        expected = self.variant_estimate - self.baseline_estimate
        if not math.isclose(self.absolute_delta, expected, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("absolute_delta must equal variant minus baseline")
        if self.interval_high < self.interval_low:
            raise ValueError("interval_high cannot be below interval_low")
        if not self.interval_low <= self.absolute_delta <= self.interval_high:
            raise ValueError("the uncertainty interval must contain absolute_delta")
        if self.baseline_estimate == 0.0 and self.relative_delta is not None:
            raise ValueError("relative_delta must be null when baseline_estimate is zero")
        if self.baseline_estimate != 0.0:
            expected_relative = self.absolute_delta / self.baseline_estimate
            if self.relative_delta is None or not math.isclose(
                self.relative_delta, expected_relative, rel_tol=1e-12, abs_tol=1e-12
            ):
                raise ValueError("relative_delta is inconsistent with the estimates")
        _require_unique(self.outcome_snapshot_hashes, "outcome_snapshot_hashes")
        return self

    @property
    def signal_hash(self) -> str:
        return self.content_hash


class AuctionScenarioRecord(SignalContract):
    """Canonical disclosure record for a runtime auction scenario."""

    scenario_id: str = Field(min_length=1)
    scenario_version: str = Field(min_length=1)
    query_contexts: tuple[str, ...] = Field(min_length=1)
    query_probabilities: tuple[float, ...] = Field(min_length=1)
    number_of_slots: int = Field(gt=0)
    billing_basis: str = Field(min_length=1)
    scoring_rule: str = Field(min_length=1)
    mechanism: Mechanism
    floor_or_reserve: float = Field(ge=0.0)
    bid_grid: tuple[float, ...] = Field(min_length=1)
    bidder_types: tuple[str, ...] = Field(min_length=1)
    value_matrices: tuple[tuple[float, ...], ...] = Field(min_length=1)
    ctr_matrices: tuple[tuple[float, ...], ...] = Field(min_length=1)
    bidder_model: BidderModel
    horizon: int = Field(gt=0)
    burn_in: int = Field(ge=0)
    seed: int = Field(ge=0)
    data_origin: DataOrigin
    known_departures_from_production: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _scenario_dimensions_are_coherent(self) -> Self:
        query_count = len(self.query_contexts)
        bidder_count = len(self.bidder_types)
        _require_unique(self.query_contexts, "query_contexts")
        _require_unique(self.bidder_types, "bidder_types")
        if len(self.query_probabilities) != query_count:
            raise ValueError("query_probabilities must align with query_contexts")
        if not all(math.isfinite(value) and value >= 0.0 for value in self.query_probabilities):
            raise ValueError("query probabilities must be finite and non-negative")
        if not math.isclose(sum(self.query_probabilities), 1.0, abs_tol=1e-12):
            raise ValueError("query probabilities must sum to one")
        if self.number_of_slots > bidder_count:
            raise ValueError("number_of_slots cannot exceed bidder count")
        if len(self.value_matrices) != bidder_count or len(self.ctr_matrices) != bidder_count:
            raise ValueError("value and CTR matrices must contain one row per bidder")
        if any(len(row) != query_count for row in self.value_matrices):
            raise ValueError("each value matrix row must contain one value per query")
        if any(len(row) != query_count for row in self.ctr_matrices):
            raise ValueError("each CTR matrix row must contain one value per query")
        matrix_values = (*self.value_matrices, *self.ctr_matrices)
        if any(not math.isfinite(value) or value < 0.0 for row in matrix_values for value in row):
            raise ValueError("value and CTR matrix entries must be finite and non-negative")
        if any(value > 1.0 for row in self.ctr_matrices for value in row):
            raise ValueError("CTR matrix entries cannot exceed one")
        if any(not math.isfinite(bid) or bid < 0.0 for bid in self.bid_grid):
            raise ValueError("bid_grid entries must be finite and non-negative")
        if self.burn_in >= self.horizon:
            raise ValueError("burn_in must be less than horizon")
        _require_unique(
            self.known_departures_from_production,
            "known_departures_from_production",
        )
        return self

    @property
    def scenario_hash(self) -> str:
        return self.content_hash


class UncertaintyInterval(SignalContract):
    low: float
    high: float
    method: str = Field(min_length=1)

    @model_validator(mode="after")
    def _ordered_and_finite(self) -> Self:
        if not math.isfinite(self.low) or not math.isfinite(self.high):
            raise ValueError("uncertainty bounds must be finite")
        if self.high < self.low:
            raise ValueError("uncertainty high cannot be below low")
        return self


class ConvergenceRecord(SignalContract):
    """Canonical convergence disclosure emitted by the runtime simulator."""

    converged: bool
    iterations: int = Field(ge=0)
    stability_metric: float | None = None
    notes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _stability_is_finite(self) -> Self:
        if self.stability_metric is not None and not math.isfinite(self.stability_metric):
            raise ValueError("stability_metric must be finite when present")
        return self


class AuctionSensitivityRecord(SignalContract):
    """Receipt-bound summary converted from a complete runtime simulation result."""

    scenario_hash: str = Field(pattern=SHA256_PATTERN)
    baseline_signal_hash: str = Field(pattern=SHA256_PATTERN)
    variant_signal_hash: str = Field(pattern=SHA256_PATTERN)
    common_randomness_id: str = Field(min_length=1)
    mechanism: Mechanism
    bidder_model: BidderModel
    boundary_crossing_rate: float = Field(ge=0.0, le=1.0)
    allocation_change_rate: float = Field(ge=0.0, le=1.0)
    simulated_seller_revenue_baseline: float
    simulated_seller_revenue_variant: float
    simulated_advertiser_utility_baseline: float
    simulated_advertiser_utility_variant: float
    uncertainty: UncertaintyInterval
    convergence_diagnostics: ConvergenceRecord
    evidence_class: EvidenceClass = EvidenceClass.SIMULATED

    @model_validator(mode="after")
    def _result_is_simulated_and_finite(self) -> Self:
        if self.evidence_class is not EvidenceClass.SIMULATED:
            raise ValueError("auction sensitivity evidence_class must be SIMULATED")
        values = (
            self.simulated_seller_revenue_baseline,
            self.simulated_seller_revenue_variant,
            self.simulated_advertiser_utility_baseline,
            self.simulated_advertiser_utility_variant,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("auction sensitivity economics must be finite")
        return self

    @property
    def result_hash(self) -> str:
        return self.content_hash


class SignalGateResult(SignalContract):
    gate: str = Field(pattern=GATE_PATTERN)
    passed: bool
    code: str = Field(pattern=GATE_CODE_PATTERN)
    detail: str = ""
    coerce_to: NextAction | None = None
    security_signal: bool = False

    @model_validator(mode="after")
    def _gate_code_and_outcome_are_coherent(self) -> Self:
        if not self.code.startswith(f"{self.gate}_"):
            raise ValueError("gate code must use the same IS prefix as gate")
        if self.passed and self.code != f"{self.gate}_OK":
            raise ValueError("a passing gate must use its stable OK code")
        if self.passed and self.coerce_to is not None:
            raise ValueError("a passing gate cannot coerce the action")
        if not self.passed and self.code == f"{self.gate}_OK":
            raise ValueError("a failing gate cannot use an OK code")
        if not self.passed and self.coerce_to is None:
            raise ValueError("a failing gate must declare a fail-closed action")
        return self

    def __bool__(self) -> bool:
        return self.passed


class HumanApproval(SignalContract):
    approval_id: str = Field(min_length=1)
    receipt_id: str = Field(min_length=1)
    previous_receipt_sha256: str = Field(pattern=SHA256_PATTERN)
    actor_id: str = Field(min_length=1)
    authorized_action: NextAction
    reason_code: str = Field(min_length=1)
    comment: str = ""
    approved_at: datetime

    @model_validator(mode="after")
    def _approval_time_is_aware(self) -> Self:
        _require_aware(self.approved_at, "approved_at")
        return self


class SignalDecision(SignalContract):
    evidence_class: EvidenceClass
    proposed_action: NextAction
    final_action: NextAction
    gate_results: tuple[SignalGateResult, ...] = Field(min_length=1)
    claim_wording: str = Field(min_length=1)
    rationale: str = ""

    @model_validator(mode="after")
    def _decision_matches_the_gate_chain(self) -> Self:
        gates = tuple(result.gate for result in self.gate_results)
        _require_unique(gates, "gate_results gates")
        if "IS8" not in gates:
            raise ValueError("a decision must include the evidence-action gate IS8")
        restrictiveness = {
            NextAction.TEST: 0,
            NextAction.EDIT: 1,
            NextAction.KEEP: 2,
            NextAction.HOLD: 3,
            NextAction.REVIEW: 4,
            NextAction.STOP: 5,
        }
        candidates = [self.proposed_action]
        candidates.extend(
            result.coerce_to
            for result in self.gate_results
            if not result.passed and result.coerce_to is not None
        )
        expected = max(candidates, key=restrictiveness.__getitem__)
        if self.final_action is not expected:
            raise ValueError("final_action does not match the deterministic gate chain")
        return self

    @property
    def decision_hash(self) -> str:
        return self.content_hash


class DecisionReceipt(SignalContract):
    receipt_id: str = Field(min_length=1)
    receipt_version: int = Field(ge=1)
    previous_receipt_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    tenant_id: str = Field(min_length=1)
    campaign_hash: str = Field(pattern=SHA256_PATTERN)
    family_hash: str = Field(pattern=SHA256_PATTERN)
    asset_hashes: tuple[str, ...] = Field(min_length=1)
    outcome_hashes: tuple[str, ...] = ()
    scenario_hashes: tuple[str, ...] = ()
    evidence_class: EvidenceClass
    proposed_action: NextAction
    final_action: NextAction
    gate_results: tuple[SignalGateResult, ...] = Field(min_length=1)
    human_approval: HumanApproval | None = None
    claim_wording: str = Field(min_length=1)
    cost_total_ticks: int | None = Field(default=None, ge=0)
    cost_status: CostStatus
    trace_id: str = Field(min_length=1)
    created_at: datetime
    receipt_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _receipt_is_coherent(self) -> Self:
        _require_aware(self.created_at, "created_at")
        for field_name in ("asset_hashes", "outcome_hashes", "scenario_hashes"):
            values = getattr(self, field_name)
            if any(not re.fullmatch(SHA256_PATTERN, value) for value in values):
                raise ValueError(f"{field_name} must contain SHA-256 digests")
            _require_unique(values, field_name)
        if self.receipt_version == 1 and self.previous_receipt_sha256 is not None:
            raise ValueError("receipt version 1 cannot link to a previous receipt")
        if self.receipt_version > 1 and self.previous_receipt_sha256 is None:
            raise ValueError("receipt revisions must link to the previous receipt digest")
        if self.cost_status is CostStatus.UNKNOWN and self.cost_total_ticks is not None:
            raise ValueError("unknown total cost must be null")
        if self.cost_status is not CostStatus.UNKNOWN and self.cost_total_ticks is None:
            raise ValueError("known or estimated total cost requires a value")
        decision = SignalDecision(
            schema_version=self.schema_version,
            evidence_class=self.evidence_class,
            proposed_action=self.proposed_action,
            final_action=self.final_action,
            gate_results=self.gate_results,
            claim_wording=self.claim_wording,
        )
        if self.human_approval is not None:
            if self.human_approval.receipt_id != self.receipt_id:
                raise ValueError("human approval is attached to another receipt")
            if self.human_approval.previous_receipt_sha256 != self.previous_receipt_sha256:
                raise ValueError("human approval does not bind the previous receipt")
            if self.human_approval.authorized_action is not decision.final_action:
                raise ValueError("human approval action does not match final_action")
        unsigned = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if content_sha256(unsigned) != self.receipt_sha256:
            raise ValueError("receipt_sha256 does not match the receipt content")
        return self

    @property
    def content_hash(self) -> str:
        return self.receipt_sha256
