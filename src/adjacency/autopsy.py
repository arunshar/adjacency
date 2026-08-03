"""Artifact-backed data model for the offline Autopsy demo."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from adjacency.baseline import BaselineBlocklist, BaselineMatcher
from adjacency.contracts import (
    SEVERITY_ACTION,
    Action,
    DeltaKind,
    DeltaRow,
    Frozen,
    ImageEvidence,
    InventoryItem,
    PolicySpec,
    Verdict,
)
from adjacency.corpus import FrozenCorpus, load_frozen_corpus
from adjacency.delta import BaselineDecision, DeltaEngine

GATE_FAIL_BEAT = "G1_SPAN_NOT_FOUND"


class AutopsyDataError(ValueError):
    """Raised when bundled UI artifacts disagree or are incomplete."""


class GateAudit(Frozen):
    gate: str = Field(min_length=1)
    passed: bool
    code: str | None = None
    coerce_to: Action | None = None
    detail: str = ""


class TraceArtifact(Frozen):
    item_id: str = Field(min_length=1)
    final_verdict: Verdict
    low_verdict: Verdict | None = None
    gate_results: tuple[GateAudit, ...]
    escalation_reasons: tuple[str, ...] = ()
    matched_terms: tuple[str, ...] = ()
    model_calls: tuple[dict[str, Any], ...] = ()
    model_errors: tuple[str, ...] = ()
    tier_zero_code: str = Field(min_length=1)

    @property
    def failed_gate_codes(self) -> tuple[str, ...]:
        return tuple(
            result.code for result in self.gate_results if not result.passed and result.code
        )


class EconomicsAssumption(Frozen):
    schema_version: Literal[1] = 1
    currency: Literal["USD"] = "USD"
    default_value_per_recovered_item_usd: Decimal = Field(ge=0)
    description: str = Field(min_length=1)
    evidence_class: Literal["illustrative_demo_input"] = "illustrative_demo_input"


@dataclass(frozen=True, slots=True)
class AutopsyRecord:
    root: Path
    item: InventoryItem
    source_url: str
    trace: TraceArtifact
    baseline: BaselineDecision
    delta: DeltaRow

    @property
    def trace_id(self) -> str:
        return f"trace:{self.item.item_id}"

    @property
    def pre_gate_action(self) -> Action:
        if self.trace.failed_gate_codes:
            return SEVERITY_ACTION[self.trace.final_verdict.severity]
        return self.trace.final_verdict.action

    @property
    def pre_gate_delta(self) -> DeltaRow:
        return DeltaRow(
            item_id=self.item.item_id,
            engine_action=self.pre_gate_action,
            baseline_action=self.baseline.action,
            matched_terms=self.baseline.matched_terms,
        )


@dataclass(frozen=True, slots=True)
class AutopsyBundle:
    root: Path
    corpus: FrozenCorpus
    policy: PolicySpec
    blocklist: BaselineBlocklist
    corpus_hash: str
    policy_hash: str
    records: tuple[AutopsyRecord, ...]
    wow_item_id: str
    economics: EconomicsAssumption

    def record(self, item_id: str) -> AutopsyRecord:
        for record in self.records:
            if record.item.item_id == item_id:
                return record
        raise AutopsyDataError(f"unknown autopsy item id: {item_id}")

    @property
    def final_delta_counts(self) -> dict[str, int]:
        counts = Counter(record.delta.kind.value for record in self.records)
        return {kind.value: counts[kind.value] for kind in DeltaKind}


class GatePhase(StrEnum):
    PENDING = "pending"
    PRE_GATE = "pre_gate"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class DemoFrame:
    visible_item_ids: tuple[str, ...] = ()
    gate_phase: GatePhase = GatePhase.PENDING


@dataclass(frozen=True, slots=True)
class FrameView:
    agree: tuple[AutopsyRecord, ...]
    over_block: tuple[AutopsyRecord, ...]
    under_block: tuple[AutopsyRecord, ...]
    hitl: tuple[AutopsyRecord, ...]
    gate_fail: AutopsyRecord | None


class AutopsyDemo:
    """Build deterministic streaming frames from the committed demo artifacts."""

    def __init__(self, bundle: AutopsyBundle) -> None:
        self.bundle = bundle

    def frames(self) -> tuple[DemoFrame, ...]:
        wow = self.bundle.record(self.bundle.wow_item_id)
        ordinary = [
            record
            for record in self.bundle.records
            if record.item.item_id != wow.item.item_id
            and not record.trace.failed_gate_codes
            and record.trace.final_verdict.action is not Action.REVIEW
        ]
        deferred = [
            record
            for record in self.bundle.records
            if record.item.item_id != wow.item.item_id and record not in ordinary
        ]
        midpoint = len(ordinary) // 2
        ordered = [*ordinary[:midpoint], wow, *ordinary[midpoint:], *deferred]

        frames = [DemoFrame()]
        visible: list[str] = []
        for record in ordered:
            visible.append(record.item.item_id)
            if record.item.item_id == wow.item.item_id:
                frames.append(DemoFrame(tuple(visible), GatePhase.PRE_GATE))
                frames.append(DemoFrame(tuple(visible), GatePhase.FAILED))
            else:
                phase = GatePhase.FAILED if wow.item.item_id in visible else GatePhase.PENDING
                frames.append(DemoFrame(tuple(visible), phase))
        return tuple(frames)

    def view(self, frame: DemoFrame) -> FrameView:
        columns: dict[DeltaKind, list[AutopsyRecord]] = {kind: [] for kind in DeltaKind}
        hitl: list[AutopsyRecord] = []
        gate_fail: AutopsyRecord | None = None
        for item_id in frame.visible_item_ids:
            record = self.bundle.record(item_id)
            if item_id == self.bundle.wow_item_id and frame.gate_phase is GatePhase.PRE_GATE:
                columns[record.pre_gate_delta.kind].append(record)
                continue
            if item_id == self.bundle.wow_item_id and frame.gate_phase is GatePhase.FAILED:
                gate_fail = record
            else:
                columns[record.delta.kind].append(record)
            if record.trace.final_verdict.action is Action.REVIEW:
                hitl.append(record)
        return FrameView(
            agree=tuple(columns[DeltaKind.AGREE]),
            over_block=tuple(columns[DeltaKind.OVER_BLOCK]),
            under_block=tuple(columns[DeltaKind.UNDER_BLOCK]),
            hitl=tuple(hitl),
            gate_fail=gate_fail,
        )


def load_autopsy_bundle(root: Path | str) -> AutopsyBundle:
    repo_root = Path(root).resolve()
    corpus_path = repo_root / "corpus" / "frozen" / "manifest.json"
    try:
        corpus = load_frozen_corpus(corpus_path, verify_media_root=repo_root)
    except (OSError, KeyError, ValueError) as error:
        raise AutopsyDataError(f"cannot read Autopsy artifact: {corpus_path}") from error
    policy_document = _read_object(repo_root / "artifacts" / "tuesday" / "policy_spec.json")
    blocklist_document = _read_object(
        repo_root / "artifacts" / "tuesday" / "baseline_blocklist.json"
    )
    trace_document = _read_object(repo_root / "artifacts" / "wednesday" / "judge_traces.json")
    economics_document = _read_object(repo_root / "artifacts" / "ui" / "economics_assumption.json")
    try:
        policy = PolicySpec.model_validate(policy_document["policy_spec"])
        blocklist = BaselineBlocklist.model_validate(blocklist_document["baseline_blocklist"])
        traces = tuple(TraceArtifact.model_validate(value) for value in trace_document["traces"])
        economics = EconomicsAssumption.model_validate(economics_document)
    except (KeyError, TypeError, ValueError) as error:
        raise AutopsyDataError("Autopsy artifacts have an invalid shape") from error

    if policy.policy_hash != blocklist.policy_hash:
        raise AutopsyDataError("compiled policy and baseline hashes differ")
    if trace_document.get("policy_hash") != policy.policy_hash:
        raise AutopsyDataError("judge trace policy hash differs from the compiled policy")
    if trace_document.get("corpus_hash") != corpus.corpus_hash:
        raise AutopsyDataError("judge trace corpus hash differs from the frozen corpus")

    trace_by_id = {trace.item_id: trace for trace in traces}
    item_ids = {item.item_id for item in corpus.items}
    if len(trace_by_id) != len(traces) or set(trace_by_id) != item_ids:
        raise AutopsyDataError("judge traces do not map one-to-one onto the frozen corpus")

    baseline = BaselineMatcher(blocklist).match_all(corpus.items)
    verdicts = tuple(trace_by_id[item.item_id].final_verdict for item in corpus.items)
    deltas = DeltaEngine().compare(verdicts, baseline)
    corpus_record_by_id = {record.item.item_id: record for record in corpus.records}
    records = tuple(
        AutopsyRecord(
            root=repo_root,
            item=item,
            source_url=corpus_record_by_id[item.item_id].source_url,
            trace=trace_by_id[item.item_id],
            baseline=baseline[item.item_id],
            delta=delta,
        )
        for item, delta in zip(corpus.items, deltas, strict=True)
    )
    wow_candidates = [
        record
        for record in records
        if GATE_FAIL_BEAT in record.trace.failed_gate_codes
        and record.pre_gate_action is Action.ALLOW
        and record.trace.final_verdict.action is Action.REVIEW
        and record.item.has_media
        and any(
            isinstance(evidence, ImageEvidence) for evidence in record.trace.final_verdict.evidence
        )
    ]
    if not wow_candidates:
        raise AutopsyDataError("no artifact-backed G1 gate-fail demo item is available")

    return AutopsyBundle(
        root=repo_root,
        corpus=corpus,
        policy=policy,
        blocklist=blocklist,
        corpus_hash=corpus.corpus_hash,
        policy_hash=policy.policy_hash,
        records=records,
        wow_item_id=wow_candidates[0].item.item_id,
        economics=economics,
    )


def audit_payload(record: AutopsyRecord) -> dict[str, object]:
    return {
        "baseline": {
            "action": record.baseline.action.value,
            "matched_terms": list(record.baseline.matched_terms),
        },
        "delta_kind": record.delta.kind.value,
        "display_only_rationale": record.trace.final_verdict.rationale,
        "escalation_reasons": list(record.trace.escalation_reasons),
        "final_verdict": record.trace.final_verdict.model_dump(mode="json"),
        "gate_chain": [result.model_dump(mode="json") for result in record.trace.gate_results],
        "item_id": record.item.item_id,
        "model_calls": list(record.trace.model_calls),
        "source_artifacts": [
            "artifacts/wednesday/judge_traces.json",
            "corpus/frozen/manifest.json",
            "artifacts/tuesday/baseline_blocklist.json",
        ],
        "source_url": record.source_url,
        "trace_id": record.trace_id,
    }


def render_evidence_image(record: AutopsyRecord):
    if not record.item.media:
        return None
    media = record.item.media[0]
    if not media.local_path:
        return None
    from PIL import Image, ImageDraw

    candidate = (record.root / media.local_path).resolve()
    if not candidate.is_relative_to(record.root) or not candidate.is_file():
        raise AutopsyDataError(f"local media is unavailable: {media.local_path}")
    image = Image.open(candidate).convert("RGB")
    draw = ImageDraw.Draw(image)
    for evidence in record.trace.final_verdict.evidence:
        if (
            isinstance(evidence, ImageEvidence)
            and evidence.media_id == record.item.media[0].media_id
        ):
            draw.rectangle(
                (
                    evidence.x,
                    evidence.y,
                    evidence.x + evidence.w,
                    evidence.y + evidence.h,
                ),
                outline=(220, 38, 38),
                width=max(3, min(image.size) // 160),
            )
    return image


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AutopsyDataError(f"cannot read Autopsy artifact: {path}") from error
    if not isinstance(value, dict):
        raise AutopsyDataError(f"Autopsy artifact is not an object: {path}")
    return value
