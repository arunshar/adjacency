"""Measured metadata for one recorded model response."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

COST_TICKS_PER_USD = 10_000_000_000


@dataclass(frozen=True, slots=True)
class ModelCallMeasurement:
    surface: str
    model: str
    reasoning_effort: str
    elapsed_ms: float
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    total_tokens: int
    cost_in_usd_ticks: int
    response_id: str | None

    @property
    def cost_usd(self) -> float:
        return self.cost_in_usd_ticks / COST_TICKS_PER_USD

    def as_dict(self) -> dict[str, object]:
        return {
            "cost_in_usd_ticks": self.cost_in_usd_ticks,
            "cost_usd": self.cost_usd,
            "elapsed_ms": self.elapsed_ms,
            "input_tokens": self.input_tokens,
            "model": self.model,
            "output_tokens": self.output_tokens,
            "reasoning_effort": self.reasoning_effort,
            "reasoning_tokens": self.reasoning_tokens,
            "response_id": self.response_id,
            "surface": self.surface,
            "total_tokens": self.total_tokens,
        }


def measurement_from_response(
    response: Mapping[str, Any],
    *,
    surface: str,
    reasoning_effort: str,
    elapsed_ms: float,
) -> ModelCallMeasurement:
    usage = response.get("usage")
    usage_map = usage if isinstance(usage, Mapping) else {}
    output_details = usage_map.get("output_tokens_details")
    output_map = output_details if isinstance(output_details, Mapping) else {}
    response_id = response.get("id")
    return ModelCallMeasurement(
        surface=surface,
        model=str(response.get("model") or "unknown"),
        reasoning_effort=reasoning_effort,
        elapsed_ms=elapsed_ms,
        input_tokens=_integer(usage_map.get("input_tokens")),
        output_tokens=_integer(usage_map.get("output_tokens")),
        reasoning_tokens=_integer(output_map.get("reasoning_tokens")),
        total_tokens=_integer(usage_map.get("total_tokens")),
        cost_in_usd_ticks=_integer(usage_map.get("cost_in_usd_ticks")),
        response_id=str(response_id) if response_id is not None else None,
    )


def _integer(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0
