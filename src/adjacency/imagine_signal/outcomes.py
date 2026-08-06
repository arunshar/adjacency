"""Aggregate outcome admission and deterministic signal estimation.

The offline MVP deliberately consumes snapshots, not user-level events. Callers
provide the reference clock and expected join keys so replay remains deterministic.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from threading import Lock
from typing import Any

from adjacency.imagine_signal.canonical import content_sha256
from adjacency.imagine_signal.contracts import (
    DataOrigin,
    EvidenceClass,
    MeasurementWindow,
    OutcomeSnapshot,
    SignalEstimate,
)


class OutcomeErrorCode(StrEnum):
    """Stable failure codes surfaced by outcome admission and estimation."""

    DUPLICATE_CONFLICT = "IS5_DUPLICATE_CONFLICT"
    TENANT_MISMATCH = "IS5_TENANT_MISMATCH"
    CAMPAIGN_MISMATCH = "IS5_CAMPAIGN_MISMATCH"
    CREATIVE_MISMATCH = "IS5_CREATIVE_MISMATCH"
    CONTEXT_MISMATCH = "IS5_CONTEXT_MISMATCH"
    EXPERIMENT_MISMATCH = "IS5_EXPERIMENT_MISMATCH"
    ARM_MISMATCH = "IS5_ARM_MISMATCH"
    WINDOW_MISMATCH = "IS5_WINDOW_MISMATCH"
    FUTURE_OBSERVATION = "IS5_FUTURE_OBSERVATION"
    STALE = "IS5_OUTCOME_STALE"
    PAIR_MISMATCH = "IS6_OUTCOME_PAIR_MISMATCH"
    ZERO_DENOMINATOR = "IS6_ZERO_DENOMINATOR"
    UNSUPPORTED_ORIGIN = "IS6_UNSUPPORTED_ORIGIN"
    FIXTURE_INVALID = "IS5_FIXTURE_INVALID"


class OutcomeValidationError(ValueError):
    """Outcome failure carrying a stable machine-readable code."""

    def __init__(self, code: OutcomeErrorCode, detail: str) -> None:
        super().__init__(f"{code.value}: {detail}")
        self.code = code
        self.detail = detail


class AppendStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    DUPLICATE = "DUPLICATE"


@dataclass(frozen=True, slots=True)
class AppendOutcomeResult:
    """Result of an idempotent aggregate-snapshot append."""

    status: AppendStatus
    snapshot_hash: str


@dataclass(frozen=True, slots=True)
class OutcomeExpectation:
    """Join and freshness constraints supplied by the campaign controller."""

    tenant_id: str
    campaign_id: str
    creative_id: str
    context_id: str
    experiment_id: str
    arm_id: str
    measurement_window: MeasurementWindow
    now: datetime
    max_age: timedelta

    def __post_init__(self) -> None:
        if self.now.tzinfo is None or self.now.utcoffset() is None:
            raise ValueError("now must include a UTC offset")
        if self.max_age < timedelta(0):
            raise ValueError("max_age cannot be negative")


@dataclass(frozen=True, slots=True)
class FrozenOutcomeFixture:
    """Verified, synthetic aggregate snapshots loaded from one committed file."""

    description: str
    snapshots: tuple[OutcomeSnapshot, ...]


class InMemoryOutcomeRepository:
    """Thread-safe prototype repository with append-once snapshot identity.

    The source snapshot ID is an idempotency key within a tenant. Reusing it with
    different content is corruption, not a newer version.
    """

    def __init__(self) -> None:
        self._snapshots: dict[tuple[str, str], OutcomeSnapshot] = {}
        self._lock = Lock()

    def append_once(self, snapshot: OutcomeSnapshot) -> AppendOutcomeResult:
        key = (snapshot.tenant_id, snapshot.source_snapshot_id)
        with self._lock:
            existing = self._snapshots.get(key)
            if existing is None:
                self._snapshots[key] = snapshot
                return AppendOutcomeResult(AppendStatus.ACCEPTED, snapshot.snapshot_hash)
            if existing.snapshot_hash == snapshot.snapshot_hash:
                return AppendOutcomeResult(AppendStatus.DUPLICATE, snapshot.snapshot_hash)
        raise OutcomeValidationError(
            OutcomeErrorCode.DUPLICATE_CONFLICT,
            "source_snapshot_id was already admitted with different content",
        )

    def get(self, tenant_id: str, source_snapshot_id: str) -> OutcomeSnapshot | None:
        with self._lock:
            return self._snapshots.get((tenant_id, source_snapshot_id))

    def snapshots(self, tenant_id: str) -> tuple[OutcomeSnapshot, ...]:
        with self._lock:
            selected = [
                snapshot
                for (snapshot_tenant, _), snapshot in self._snapshots.items()
                if snapshot_tenant == tenant_id
            ]
        return tuple(sorted(selected, key=lambda item: item.source_snapshot_id))


def load_frozen_outcome_fixture(path: Path | str) -> FrozenOutcomeFixture:
    """Load and verify the closed demo fixture shape and source payload digests."""

    fixture_path = Path(path)
    try:
        document = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise OutcomeValidationError(
            OutcomeErrorCode.FIXTURE_INVALID,
            f"cannot read outcome fixture: {error}",
        ) from error
    required = {
        "description",
        "evidence_class",
        "fixture_version",
        "source_payloads",
        "snapshots",
    }
    if not isinstance(document, dict) or set(document) != required:
        raise OutcomeValidationError(
            OutcomeErrorCode.FIXTURE_INVALID,
            "outcome fixture must use the exact version 1 field set",
        )
    if (
        document["fixture_version"] != 1
        or document["evidence_class"] != EvidenceClass.FROZEN_REPLAY.value
        or not isinstance(document["description"], str)
        or not document["description"].strip()
        or not isinstance(document["source_payloads"], list)
        or not isinstance(document["snapshots"], list)
    ):
        raise OutcomeValidationError(
            OutcomeErrorCode.FIXTURE_INVALID,
            "outcome fixture metadata is invalid",
        )

    payloads: dict[str, dict[str, Any]] = {}
    for payload in document["source_payloads"]:
        if not isinstance(payload, dict) or set(payload) != {
            "source_snapshot_id",
            "impressions",
            "clicks",
        }:
            raise OutcomeValidationError(
                OutcomeErrorCode.FIXTURE_INVALID,
                "source payload has an invalid shape",
            )
        source_snapshot_id = payload.get("source_snapshot_id")
        if not isinstance(source_snapshot_id, str) or source_snapshot_id in payloads:
            raise OutcomeValidationError(
                OutcomeErrorCode.FIXTURE_INVALID,
                "source payload IDs must be nonempty and unique",
            )
        payloads[source_snapshot_id] = payload

    try:
        snapshots = tuple(_snapshot_from_json_record(item) for item in document["snapshots"])
    except (TypeError, ValueError) as error:
        raise OutcomeValidationError(
            OutcomeErrorCode.FIXTURE_INVALID,
            f"snapshot contract validation failed: {error}",
        ) from error
    if not snapshots:
        raise OutcomeValidationError(
            OutcomeErrorCode.FIXTURE_INVALID,
            "outcome fixture must contain at least one snapshot",
        )
    if len({item.source_snapshot_id for item in snapshots}) != len(snapshots):
        raise OutcomeValidationError(
            OutcomeErrorCode.FIXTURE_INVALID,
            "snapshot IDs must be unique within the fixture",
        )
    if set(payloads) != {item.source_snapshot_id for item in snapshots}:
        raise OutcomeValidationError(
            OutcomeErrorCode.FIXTURE_INVALID,
            "source payloads must pair exactly with snapshots",
        )
    for snapshot in snapshots:
        if content_sha256(payloads[snapshot.source_snapshot_id]) != snapshot.source_sha256:
            raise OutcomeValidationError(
                OutcomeErrorCode.FIXTURE_INVALID,
                f"source digest mismatch for {snapshot.source_snapshot_id}",
            )
    return FrozenOutcomeFixture(document["description"].strip(), snapshots)


def _snapshot_from_json_record(value: object) -> OutcomeSnapshot:
    if not isinstance(value, dict):
        raise TypeError("snapshot must be a JSON object")
    parsed = dict(value)
    origin = parsed.get("origin")
    if not isinstance(origin, str):
        raise TypeError("snapshot origin must be a string")
    parsed["origin"] = DataOrigin(origin)
    for field_name in ("measurement_start", "measurement_end", "observed_at"):
        encoded = parsed.get(field_name)
        if not isinstance(encoded, str):
            raise TypeError(f"{field_name} must be an ISO-8601 string")
        parsed[field_name] = datetime.fromisoformat(encoded)
    return OutcomeSnapshot.model_validate(parsed)


def validate_snapshot(snapshot: OutcomeSnapshot, expected: OutcomeExpectation) -> None:
    """Fail closed when a snapshot cannot join exactly to its declared arm."""

    checks = (
        (
            snapshot.tenant_id == expected.tenant_id,
            OutcomeErrorCode.TENANT_MISMATCH,
            "tenant_id does not match",
        ),
        (
            snapshot.campaign_id == expected.campaign_id,
            OutcomeErrorCode.CAMPAIGN_MISMATCH,
            "campaign_id does not match",
        ),
        (
            snapshot.creative_id == expected.creative_id,
            OutcomeErrorCode.CREATIVE_MISMATCH,
            "creative_id does not match",
        ),
        (
            snapshot.context_id == expected.context_id,
            OutcomeErrorCode.CONTEXT_MISMATCH,
            "context_id does not match",
        ),
        (
            snapshot.experiment_id == expected.experiment_id,
            OutcomeErrorCode.EXPERIMENT_MISMATCH,
            "experiment_id does not match",
        ),
        (
            snapshot.arm_id == expected.arm_id,
            OutcomeErrorCode.ARM_MISMATCH,
            "arm_id does not match",
        ),
        (
            snapshot.measurement_start == expected.measurement_window.start
            and snapshot.measurement_end == expected.measurement_window.end,
            OutcomeErrorCode.WINDOW_MISMATCH,
            "measurement window does not match the registered window",
        ),
    )
    for passed, code, detail in checks:
        if not passed:
            raise OutcomeValidationError(code, detail)
    if snapshot.observed_at > expected.now:
        raise OutcomeValidationError(
            OutcomeErrorCode.FUTURE_OBSERVATION,
            "observed_at is later than the supplied reference clock",
        )
    if expected.now - snapshot.observed_at > expected.max_age:
        raise OutcomeValidationError(
            OutcomeErrorCode.STALE,
            "snapshot is older than the admitted freshness interval",
        )


def estimate_ctr_difference(
    baseline: OutcomeSnapshot,
    variant: OutcomeSnapshot,
) -> SignalEstimate:
    """Compare aggregate CTR with a transparent paired-window approximation.

    This function estimates a response difference only. It does not estimate an
    auction effect, publisher revenue, or causal lift. The 95 percent interval is
    the independent-binomial Wald approximation, clipped to the valid difference
    range. A future randomized analysis should replace it with the approved
    experiment platform estimator.
    """

    _validate_estimation_pair(baseline, variant)
    if baseline.impressions == 0 or variant.impressions == 0:
        raise OutcomeValidationError(
            OutcomeErrorCode.ZERO_DENOMINATOR,
            "CTR is unavailable when either snapshot has zero impressions",
        )

    baseline_rate = baseline.clicks / baseline.impressions
    variant_rate = variant.clicks / variant.impressions
    delta = variant_rate - baseline_rate
    standard_error = math.sqrt(
        baseline_rate * (1.0 - baseline_rate) / baseline.impressions
        + variant_rate * (1.0 - variant_rate) / variant.impressions
    )
    margin = 1.959963984540054 * standard_error
    interval_low = max(-1.0, delta - margin)
    interval_high = min(1.0, delta + margin)
    relative_delta = None if baseline_rate == 0.0 else delta / baseline_rate

    return SignalEstimate(
        schema_version="1",
        baseline_creative_id=baseline.creative_id,
        variant_creative_id=variant.creative_id,
        context_id=baseline.context_id,
        metric="observed.ctr",
        baseline_estimate=baseline_rate,
        variant_estimate=variant_rate,
        absolute_delta=delta,
        relative_delta=relative_delta,
        interval_low=interval_low,
        interval_high=interval_high,
        method="aggregate_independent_binomial_wald_95",
        sample_size=baseline.impressions + variant.impressions,
        evidence_class=EvidenceClass.FROZEN_REPLAY,
        outcome_snapshot_hashes=(baseline.snapshot_hash, variant.snapshot_hash),
    )


def _validate_estimation_pair(
    baseline: OutcomeSnapshot,
    variant: OutcomeSnapshot,
) -> None:
    shared_fields = (
        "tenant_id",
        "campaign_id",
        "context_id",
        "experiment_id",
        "origin",
        "measurement_start",
        "measurement_end",
        "attribution_method",
    )
    mismatched = [
        field_name
        for field_name in shared_fields
        if getattr(baseline, field_name) != getattr(variant, field_name)
    ]
    if mismatched:
        raise OutcomeValidationError(
            OutcomeErrorCode.PAIR_MISMATCH,
            f"snapshots differ on required pair fields: {', '.join(mismatched)}",
        )
    if baseline.creative_id == variant.creative_id or baseline.arm_id == variant.arm_id:
        raise OutcomeValidationError(
            OutcomeErrorCode.PAIR_MISMATCH,
            "baseline and variant require distinct creative_id and arm_id values",
        )
    if baseline.origin not in (DataOrigin.SYNTHETIC, DataOrigin.FROZEN_REPLAY):
        raise OutcomeValidationError(
            OutcomeErrorCode.UNSUPPORTED_ORIGIN,
            "the offline estimator accepts only synthetic or frozen replay snapshots",
        )
