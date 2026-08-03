"""Multimodal policy judging with deterministic tier escalation."""

from __future__ import annotations

import base64
import json
import mimetypes
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from statistics import median
from typing import Any

from adjacency.baseline import BaselineMatcher
from adjacency.contracts import Action, InventoryItem, PolicySpec, Verdict
from adjacency.gates import GateChainResult, run_verdict_gates
from adjacency.model_metrics import ModelCallMeasurement, measurement_from_response
from adjacency.near_dup import NearDupGroup
from adjacency.tier_zero import TierZeroCode, decide_tier_zero
from adjacency.xai import ResponseClient, output_text

TIER_ONE_SURFACE = "model.adjacency_judge.tier1"
TIER_TWO_SURFACE = "model.adjacency_judge.tier2"


class EscalationReason(StrEnum):
    LOW_CONFIDENCE = "low_confidence"
    BOUNDARY_SEVERITY = "boundary_severity"
    MEDIA_WITH_CLEAN_TEXT = "media_with_clean_text"
    CLUSTER_DISAGREEMENT = "cluster_disagreement"
    LOW_TIER_GATE_FAILURE = "low_tier_gate_failure"
    MODEL_FAILURE = "model_failure"


class JudgeOutputError(ValueError):
    """Raised when a model changes a trusted verdict field."""


@dataclass(frozen=True, slots=True)
class JudgeTrace:
    item_id: str
    verdict: Verdict
    gate_result: GateChainResult
    tier_zero_code: TierZeroCode
    matched_terms: tuple[str, ...]
    escalation_reasons: tuple[EscalationReason, ...] = ()
    model_calls: tuple[ModelCallMeasurement, ...] = ()
    low_verdict: Verdict | None = None
    model_errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _ModelResult:
    verdict: Verdict
    gate_result: GateChainResult
    measurement: ModelCallMeasurement
    error: str | None = None


class AdjacencyJudge:
    """Judge one item at a time and escalate only on explicit predicates."""

    def __init__(
        self,
        client: ResponseClient,
        spec: PolicySpec,
        baseline_matcher: BaselineMatcher,
        *,
        media_root: Path | str = ".",
        model: str = "grok-4.5",
        confidence_threshold: float = 0.6,
    ) -> None:
        self.client = client
        self.spec = spec
        self.baseline_matcher = baseline_matcher
        self.media_root = Path(media_root).resolve()
        self.model = model
        self.confidence_threshold = confidence_threshold

    def judge(
        self,
        item: InventoryItem,
        *,
        has_carve_out: bool = False,
        cluster_disagreement: bool = False,
    ) -> JudgeTrace:
        baseline = self.baseline_matcher.match(item)
        tier_zero = decide_tier_zero(
            item,
            policy_version=self.spec.version,
            matched_terms=baseline.matched_terms,
            has_carve_out=has_carve_out,
        )
        if tier_zero.decided and not cluster_disagreement:
            if tier_zero.verdict is None:
                raise RuntimeError("decided Tier 0 result has no verdict")
            gated = run_verdict_gates(tier_zero.verdict, item, self.spec)
            return JudgeTrace(
                item_id=item.item_id,
                verdict=gated.verdict,
                gate_result=gated,
                tier_zero_code=tier_zero.code,
                matched_terms=baseline.matched_terms,
            )

        low = self._model_judge(item, tier=1)
        reasons = list(self._escalation_reasons(item, baseline.matched_terms, low))
        if cluster_disagreement:
            reasons.append(EscalationReason.CLUSTER_DISAGREEMENT)
        if not reasons:
            return JudgeTrace(
                item_id=item.item_id,
                verdict=low.gate_result.verdict,
                gate_result=low.gate_result,
                tier_zero_code=tier_zero.code,
                matched_terms=baseline.matched_terms,
                model_calls=(low.measurement,),
                low_verdict=low.verdict,
                model_errors=(low.error,) if low.error else (),
            )

        high = self._model_judge(
            item,
            tier=2,
            prior=low.verdict,
            reasons=tuple(reasons),
        )
        gated = run_verdict_gates(
            high.verdict,
            item,
            self.spec,
            confidence_threshold=self.confidence_threshold,
            escalated=low.verdict,
        )
        errors = tuple(error for error in (low.error, high.error) if error)
        return JudgeTrace(
            item_id=item.item_id,
            verdict=gated.verdict,
            gate_result=gated,
            tier_zero_code=tier_zero.code,
            matched_terms=baseline.matched_terms,
            escalation_reasons=tuple(dict.fromkeys(reasons)),
            model_calls=(low.measurement, high.measurement),
            low_verdict=low.verdict,
            model_errors=errors,
        )

    def judge_all(
        self,
        items: Sequence[InventoryItem],
        *,
        near_dup_groups: Sequence[NearDupGroup] = (),
        max_workers: int = 1,
    ) -> tuple[JudgeTrace, ...]:
        ordered_items = tuple(items)
        if len({item.item_id for item in ordered_items}) != len(ordered_items):
            raise ValueError("inventory item ids must be unique")
        if max_workers < 1:
            raise ValueError("max_workers must be positive")
        if max_workers == 1:
            initial_traces = tuple(self.judge(item) for item in ordered_items)
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                initial_traces = tuple(executor.map(self.judge, ordered_items))
        traces = {trace.item_id: trace for trace in initial_traces}
        items_by_id = {item.item_id: item for item in ordered_items}

        for group in near_dup_groups:
            known_ids = [item_id for item_id in group.item_ids if item_id in traces]
            actions = {traces[item_id].verdict.action for item_id in known_ids}
            if len(actions) < 2:
                continue
            for item_id in known_ids:
                trace = traces[item_id]
                if trace.verdict.tier == 2:
                    if EscalationReason.CLUSTER_DISAGREEMENT not in trace.escalation_reasons:
                        traces[item_id] = replace(
                            trace,
                            escalation_reasons=(
                                *trace.escalation_reasons,
                                EscalationReason.CLUSTER_DISAGREEMENT,
                            ),
                        )
                    continue
                traces[item_id] = self._escalate_trace(
                    items_by_id[item_id],
                    trace,
                    EscalationReason.CLUSTER_DISAGREEMENT,
                )

        return tuple(traces[item.item_id] for item in ordered_items)

    def _escalate_trace(
        self,
        item: InventoryItem,
        trace: JudgeTrace,
        reason: EscalationReason,
    ) -> JudgeTrace:
        high = self._model_judge(
            item,
            tier=2,
            prior=trace.verdict,
            reasons=(reason,),
        )
        gated = run_verdict_gates(
            high.verdict,
            item,
            self.spec,
            confidence_threshold=self.confidence_threshold,
            escalated=trace.verdict,
        )
        return replace(
            trace,
            verdict=gated.verdict,
            gate_result=gated,
            escalation_reasons=(*trace.escalation_reasons, reason),
            model_calls=(*trace.model_calls, high.measurement),
            model_errors=(*trace.model_errors, *((high.error,) if high.error else ())),
        )

    def _escalation_reasons(
        self,
        item: InventoryItem,
        matched_terms: tuple[str, ...],
        result: _ModelResult,
    ) -> tuple[EscalationReason, ...]:
        reasons: list[EscalationReason] = []
        if result.verdict.confidence < self.confidence_threshold:
            reasons.append(EscalationReason.LOW_CONFIDENCE)
        if result.verdict.severity == 2:
            reasons.append(EscalationReason.BOUNDARY_SEVERITY)
        if item.has_media and not matched_terms:
            reasons.append(EscalationReason.MEDIA_WITH_CLEAN_TEXT)
        if not result.gate_result.passed:
            reasons.append(EscalationReason.LOW_TIER_GATE_FAILURE)
        if result.error:
            reasons.append(EscalationReason.MODEL_FAILURE)
        return tuple(reasons)

    def _model_judge(
        self,
        item: InventoryItem,
        *,
        tier: int,
        prior: Verdict | None = None,
        reasons: tuple[EscalationReason, ...] = (),
    ) -> _ModelResult:
        surface = TIER_ONE_SURFACE if tier == 1 else TIER_TWO_SURFACE
        effort = "low" if tier == 1 else "high"
        payload = self._payload(item, tier=tier, effort=effort, prior=prior, reasons=reasons)
        started = time.perf_counter()
        response: Mapping[str, Any] = {}
        error_message: str | None = None
        try:
            response = self.client.create(surface=surface, payload=payload)
            decoded = json.loads(output_text(response))
            verdict = Verdict.model_validate(decoded)
            self._validate_trusted_fields(verdict, item, tier=tier)
        except Exception as error:
            error_message = f"{type(error).__name__}: {error}"
            verdict = self._failure_verdict(item, tier=tier)
        elapsed_ms = (time.perf_counter() - started) * 1000
        measurement = measurement_from_response(
            response,
            surface=surface,
            reasoning_effort=effort,
            elapsed_ms=elapsed_ms,
        )
        gated = run_verdict_gates(
            verdict,
            item,
            self.spec,
            confidence_threshold=self.confidence_threshold,
            escalated=prior,
        )
        return _ModelResult(
            verdict=verdict,
            gate_result=gated,
            measurement=measurement,
            error=error_message,
        )

    def _payload(
        self,
        item: InventoryItem,
        *,
        tier: int,
        effort: str,
        prior: Verdict | None,
        reasons: tuple[EscalationReason, ...],
    ) -> Mapping[str, Any]:
        prompt = (
            "Judge whether the inventory item is safe for the advertiser policy. Return exactly "
            "one Verdict. The action must follow severity 0 or 1 to ALLOW, 2 to REVIEW, and 3 or "
            "4 to BLOCK. Cite only exact text spans from the item or bounding boxes within the "
            "provided media dimensions. Use only clause ids from the PolicySpec. The rationale "
            "is display-only. Do not claim synthetic-media detection accuracy.\n\n"
            f"Required item_id: {item.item_id}\n"
            f"Required policy_version: {self.spec.version}\n"
            f"Required tier: {tier}\n"
            f"PolicySpec:\n{self.spec.model_dump_json()}\n\n"
            f"Inventory text:\n{item.text}\n"
        )
        if prior is not None:
            prompt += (
                f"\nPrior verdict:\n{prior.model_dump_json()}\n"
                f"Escalation reasons: {[reason.value for reason in reasons]}\n"
                "Reconsider independently at high reasoning effort."
            )
        content: list[dict[str, Any]] = [{"text": prompt, "type": "input_text"}]
        for media in item.media:
            if not media.local_path:
                raise ValueError(f"media {media.media_id} has no local_path")
            content.append(
                {
                    "text": (
                        f"Media id {media.media_id}, kind {media.kind}, dimensions "
                        f"{media.width}x{media.height}."
                    ),
                    "type": "input_text",
                }
            )
            content.append(
                {
                    "detail": "high",
                    "image_url": self._data_url(media.local_path),
                    "type": "input_image",
                }
            )
        return {
            "input": [{"content": content, "role": "user"}],
            "max_output_tokens": 4096,
            "model": self.model,
            "reasoning": {"effort": effort},
            "store": False,
            "text": {
                "format": {
                    "name": "verdict",
                    "schema": Verdict.model_json_schema(),
                    "strict": True,
                    "type": "json_schema",
                }
            },
        }

    def _data_url(self, local_path: str) -> str:
        candidate = (self.media_root / local_path).resolve()
        if not candidate.is_relative_to(self.media_root):
            raise ValueError(f"media path escapes media root: {local_path}")
        data = candidate.read_bytes()
        mime_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    def _validate_trusted_fields(
        self,
        verdict: Verdict,
        item: InventoryItem,
        *,
        tier: int,
    ) -> None:
        if verdict.item_id != item.item_id:
            raise JudgeOutputError("model changed the trusted item id")
        if verdict.policy_version != self.spec.version:
            raise JudgeOutputError("model changed the trusted policy version")
        if verdict.tier != tier:
            raise JudgeOutputError("model changed the required tier")

    def _failure_verdict(self, item: InventoryItem, *, tier: int) -> Verdict:
        return Verdict(
            item_id=item.item_id,
            action=Action.REVIEW,
            severity=2,
            confidence=0.0,
            tier=tier,
            rationale="Model output failed validation. Sent to review.",
            policy_version=self.spec.version,
        )


def summarize_judge_run(
    traces: Sequence[JudgeTrace],
    *,
    corpus_hash: str,
) -> dict[str, object]:
    """Summarize tier routing, measured cost, and model-call latency."""

    if not traces:
        raise ValueError("at least one judge trace is required")
    counts = {tier: sum(trace.verdict.tier == tier for trace in traces) for tier in range(3)}
    calls = [call for trace in traces for call in trace.model_calls]
    failed_gate_counts = Counter(
        result.code for trace in traces for result in trace.gate_result.results if not result.passed
    )
    total_ticks = sum(call.cost_in_usd_ticks for call in calls)
    latencies = sorted(call.elapsed_ms for call in calls)
    return {
        "blended_cost_per_1000_decisions_usd": (total_ticks / 10_000_000_000 / len(traces) * 1000),
        "corpus_hash": corpus_hash,
        "gate_failure_code_counts": dict(sorted(failed_gate_counts.items())),
        "items_with_gate_failures": sum(not trace.gate_result.passed for trace in traces),
        "model_call_count": len(calls),
        "items_with_model_errors": sum(bool(trace.model_errors) for trace in traces),
        "model_latency_ms": {
            "p50": median(latencies) if latencies else 0.0,
            "p90": _percentile(latencies, 0.9),
            "p99": _percentile(latencies, 0.99),
        },
        "tier_distribution": {
            str(tier): {"count": counts[tier], "fraction": counts[tier] / len(traces)}
            for tier in range(3)
        },
        "total_cost_in_usd_ticks": total_ticks,
        "total_cost_usd": total_ticks / 10_000_000_000,
        "total_items": len(traces),
    }


def _percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        return 0.0
    position = (len(values) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower
    return values[lower] * (1 - weight) + values[upper] * weight
