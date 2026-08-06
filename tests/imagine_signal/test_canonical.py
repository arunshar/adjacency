"""Canonical JSON and hash vectors for ImagineSignal."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum

import pytest

from adjacency.imagine_signal.canonical import (
    canonical_json,
    canonical_json_bytes,
    canonical_payload,
    content_sha256,
    normalize_text,
)
from adjacency.imagine_signal.contracts import CostStatus, GenerationBudget

pytestmark = pytest.mark.unit


class ExampleEnum(StrEnum):
    VALUE = "value"


def test_hash_is_independent_of_mapping_construction_order():
    left = {"b": [2, 3], "a": 1}
    right = {"a": 1, "b": (2, 3)}
    assert canonical_json(left) == '{"a":1,"b":[2,3]}'
    assert content_sha256(left) == content_sha256(right)


def test_unicode_is_nfc_normalized_in_values_and_keys():
    decomposed = "café"
    assert normalize_text(decomposed) == "café"
    assert canonical_payload({decomposed: decomposed}) == {"café": "café"}


def test_sets_have_a_deterministic_order():
    assert canonical_json({"items": frozenset({"z", "a"})}) == '{"items":["a","z"]}'


def test_models_enums_dates_and_datetimes_are_supported():
    budget = GenerationBudget(
        schema_version="1",
        max_calls=1,
        max_images=1,
        max_quality_images=0,
        max_cost_in_usd_ticks=5,
        max_wallclock_ms=10,
    )
    payload = {
        "budget": budget,
        "cost": CostStatus.EXACT,
        "date": date(2026, 8, 5),
        "time": datetime(2026, 8, 5, tzinfo=UTC),
    }
    rendered = canonical_json(payload)
    assert '"cost":"EXACT"' in rendered
    assert '"date":"2026-08-05"' in rendered
    assert '"time":"2026-08-05T00:00:00Z"' in rendered


def test_canonical_bytes_are_the_utf8_encoding():
    text = canonical_json({"word": "café"})
    assert canonical_json_bytes({"word": "café"}) == text.encode("utf-8")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_floats_are_rejected(value):
    with pytest.raises(ValueError, match="non-finite"):
        canonical_json(value)


@pytest.mark.parametrize("value", [b"bytes", bytearray(b"bytes")])
def test_binary_data_is_rejected(value):
    with pytest.raises(TypeError, match="binary data"):
        canonical_json(value)


def test_non_string_mapping_keys_are_rejected():
    with pytest.raises(TypeError, match="keys must be strings"):
        canonical_json({1: "value"})


def test_keys_that_collide_after_normalization_are_rejected():
    with pytest.raises(ValueError, match="collide"):
        canonical_json({"café": 1, "café": 2})


def test_unsupported_objects_are_rejected():
    with pytest.raises(TypeError, match="unsupported canonical JSON type"):
        canonical_json(object())
