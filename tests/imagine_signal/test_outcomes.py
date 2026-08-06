from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from adjacency.imagine_signal.contracts import DataOrigin, MeasurementWindow, OutcomeSnapshot
from adjacency.imagine_signal.outcomes import (
    AppendStatus,
    InMemoryOutcomeRepository,
    OutcomeErrorCode,
    OutcomeExpectation,
    OutcomeValidationError,
    estimate_ctr_difference,
    load_frozen_outcome_fixture,
    validate_snapshot,
)

pytestmark = pytest.mark.unit

START = datetime(2026, 8, 1, tzinfo=UTC)
END = datetime(2026, 8, 2, tzinfo=UTC)
OBSERVED = datetime(2026, 8, 3, tzinfo=UTC)
SOURCE_HASH = "a" * 64


def _snapshot(**updates) -> OutcomeSnapshot:
    values = {
        "schema_version": "1",
        "tenant_id": "tenant-a",
        "campaign_id": "campaign-a",
        "creative_id": "control",
        "context_id": "home-feed",
        "experiment_id": "experiment-a",
        "arm_id": "control-arm",
        "origin": DataOrigin.SYNTHETIC,
        "measurement_start": START,
        "measurement_end": END,
        "attribution_method": "last_click_24h",
        "impressions": 1000,
        "clicks": 50,
        "conversions": 10,
        "advertiser_spend_ticks": 100_000,
        "attributed_purchase_value_ticks": 200_000,
        "source_snapshot_id": "snapshot-control",
        "source_sha256": SOURCE_HASH,
        "observed_at": OBSERVED,
    }
    values.update(updates)
    return OutcomeSnapshot(**values)


def _expectation(**updates) -> OutcomeExpectation:
    values = {
        "tenant_id": "tenant-a",
        "campaign_id": "campaign-a",
        "creative_id": "control",
        "context_id": "home-feed",
        "experiment_id": "experiment-a",
        "arm_id": "control-arm",
        "measurement_window": MeasurementWindow(
            schema_version="1",
            start=START,
            end=END,
        ),
        "now": OBSERVED + timedelta(hours=12),
        "max_age": timedelta(days=2),
    }
    values.update(updates)
    return OutcomeExpectation(**values)


def test_repository_accepts_then_deduplicates_exact_retry() -> None:
    repository = InMemoryOutcomeRepository()
    snapshot = _snapshot()

    first = repository.append_once(snapshot)
    second = repository.append_once(snapshot)

    assert first.status is AppendStatus.ACCEPTED
    assert second.status is AppendStatus.DUPLICATE
    assert first.snapshot_hash == snapshot.snapshot_hash
    assert repository.get("tenant-a", "snapshot-control") == snapshot
    assert repository.get("tenant-b", "snapshot-control") is None
    assert repository.snapshots("tenant-a") == (snapshot,)
    assert repository.snapshots("tenant-b") == ()


def test_repository_rejects_conflicting_idempotency_key() -> None:
    repository = InMemoryOutcomeRepository()
    repository.append_once(_snapshot())

    with pytest.raises(OutcomeValidationError) as error:
        repository.append_once(_snapshot(clicks=51))

    assert error.value.code is OutcomeErrorCode.DUPLICATE_CONFLICT
    assert error.value.detail


@pytest.mark.parametrize(
    ("snapshot_update", "expectation_update", "code"),
    [
        ({"tenant_id": "other"}, {}, OutcomeErrorCode.TENANT_MISMATCH),
        ({"campaign_id": "other"}, {}, OutcomeErrorCode.CAMPAIGN_MISMATCH),
        ({"creative_id": "other"}, {}, OutcomeErrorCode.CREATIVE_MISMATCH),
        ({"context_id": "other"}, {}, OutcomeErrorCode.CONTEXT_MISMATCH),
        ({"experiment_id": "other"}, {}, OutcomeErrorCode.EXPERIMENT_MISMATCH),
        ({"arm_id": "other"}, {}, OutcomeErrorCode.ARM_MISMATCH),
        (
            {"measurement_end": END + timedelta(hours=1), "observed_at": OBSERVED},
            {},
            OutcomeErrorCode.WINDOW_MISMATCH,
        ),
        (
            {"observed_at": OBSERVED + timedelta(days=1)},
            {},
            OutcomeErrorCode.FUTURE_OBSERVATION,
        ),
        (
            {},
            {"now": OBSERVED + timedelta(days=3)},
            OutcomeErrorCode.STALE,
        ),
    ],
)
def test_validate_snapshot_rejects_bad_join_or_freshness(
    snapshot_update, expectation_update, code
) -> None:
    with pytest.raises(OutcomeValidationError) as error:
        validate_snapshot(_snapshot(**snapshot_update), _expectation(**expectation_update))
    assert error.value.code is code
    assert str(error.value).startswith(code.value)


def test_validate_snapshot_accepts_exact_join() -> None:
    assert validate_snapshot(_snapshot(), _expectation()) is None


def test_expectation_requires_aware_clock_and_nonnegative_age() -> None:
    with pytest.raises(ValueError, match="UTC offset"):
        _expectation(now=datetime(2026, 8, 3))
    with pytest.raises(ValueError, match="negative"):
        _expectation(max_age=timedelta(seconds=-1))


def test_estimate_ctr_difference_is_recomputable_and_labeled() -> None:
    baseline = _snapshot()
    variant = _snapshot(
        creative_id="variant",
        arm_id="variant-arm",
        clicks=65,
        source_snapshot_id="snapshot-variant",
        source_sha256="b" * 64,
    )

    estimate = estimate_ctr_difference(baseline, variant)

    assert estimate.metric == "observed.ctr"
    assert estimate.baseline_estimate == 0.05
    assert estimate.variant_estimate == 0.065
    assert estimate.absolute_delta == pytest.approx(0.015)
    assert estimate.relative_delta == pytest.approx(0.3)
    assert estimate.interval_low < estimate.absolute_delta < estimate.interval_high
    assert estimate.sample_size == 2000
    assert estimate.outcome_snapshot_hashes == (
        baseline.snapshot_hash,
        variant.snapshot_hash,
    )


def test_estimate_uses_unavailable_relative_delta_for_zero_baseline_rate() -> None:
    estimate = estimate_ctr_difference(
        _snapshot(clicks=0),
        _snapshot(
            creative_id="variant",
            arm_id="variant-arm",
            clicks=10,
            source_snapshot_id="snapshot-variant",
            source_sha256="b" * 64,
        ),
    )
    assert estimate.relative_delta is None
    assert estimate.interval_low <= estimate.absolute_delta <= estimate.interval_high


def test_estimate_rejects_zero_denominator() -> None:
    with pytest.raises(OutcomeValidationError) as error:
        estimate_ctr_difference(
            _snapshot(impressions=0, clicks=0, conversions=0),
            _snapshot(
                creative_id="variant",
                arm_id="variant-arm",
                source_snapshot_id="snapshot-variant",
                source_sha256="b" * 64,
            ),
        )
    assert error.value.code is OutcomeErrorCode.ZERO_DENOMINATOR


@pytest.mark.parametrize(
    "variant_update",
    [
        {"context_id": "search"},
        {"creative_id": "control"},
        {"arm_id": "control-arm"},
    ],
)
def test_estimate_rejects_invalid_pair(variant_update) -> None:
    values = {
        "creative_id": "variant",
        "arm_id": "variant-arm",
        "source_snapshot_id": "snapshot-variant",
        "source_sha256": "b" * 64,
    }
    values.update(variant_update)
    with pytest.raises(OutcomeValidationError) as error:
        estimate_ctr_difference(_snapshot(), _snapshot(**values))
    assert error.value.code is OutcomeErrorCode.PAIR_MISMATCH


def test_estimate_rejects_non_offline_origin() -> None:
    baseline = _snapshot(origin=DataOrigin.SHADOW_LOG)
    variant = _snapshot(
        origin=DataOrigin.SHADOW_LOG,
        creative_id="variant",
        arm_id="variant-arm",
        source_snapshot_id="snapshot-variant",
        source_sha256="b" * 64,
    )
    with pytest.raises(OutcomeValidationError) as error:
        estimate_ctr_difference(baseline, variant)
    assert error.value.code is OutcomeErrorCode.UNSUPPORTED_ORIGIN


def test_committed_frozen_fixture_has_recomputable_source_digests() -> None:
    fixture = load_frozen_outcome_fixture(Path("fixtures/imagine_signal/outcomes/demo_family.json"))
    assert "not observations from X Ads" in fixture.description
    assert len(fixture.snapshots) == 4
    assert {snapshot.context_id for snapshot in fixture.snapshots} == {"home-feed", "search"}


@pytest.mark.parametrize(
    "mutation",
    [
        lambda document: document.update(extra=True),
        lambda document: document.update(fixture_version=2),
        lambda document: document.update(description=""),
        lambda document: document.update(source_payloads={}),
        lambda document: document.update(snapshots={}),
        lambda document: document["source_payloads"].__setitem__(0, {"bad": "shape"}),
        lambda document: document["source_payloads"].append(dict(document["source_payloads"][0])),
        lambda document: document["source_payloads"].__setitem__(
            0,
            {
                **document["source_payloads"][0],
                "source_snapshot_id": None,
            },
        ),
        lambda document: document.update(snapshots=[]),
        lambda document: document["snapshots"].append(dict(document["snapshots"][0])),
        lambda document: document["source_payloads"].pop(),
        lambda document: document["source_payloads"][0].update(clicks=401),
        lambda document: document["snapshots"][0].update(impressions="bad"),
    ],
)
def test_fixture_loader_rejects_corrupt_documents(tmp_path, mutation) -> None:
    source = Path("fixtures/imagine_signal/outcomes/demo_family.json")
    document = json.loads(source.read_text(encoding="utf-8"))
    mutation(document)
    path = tmp_path / "outcomes.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(OutcomeValidationError) as error:
        load_frozen_outcome_fixture(path)
    assert error.value.code is OutcomeErrorCode.FIXTURE_INVALID


def test_fixture_loader_rejects_missing_and_non_json_files(tmp_path) -> None:
    with pytest.raises(OutcomeValidationError) as missing:
        load_frozen_outcome_fixture(tmp_path / "missing.json")
    assert missing.value.code is OutcomeErrorCode.FIXTURE_INVALID

    malformed = tmp_path / "malformed.json"
    malformed.write_text("not json", encoding="utf-8")
    with pytest.raises(OutcomeValidationError) as invalid:
        load_frozen_outcome_fixture(malformed)
    assert invalid.value.code is OutcomeErrorCode.FIXTURE_INVALID
