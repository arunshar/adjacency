"""Two-run free-text policy baseline over an identical frozen corpus."""

from __future__ import annotations

import base64
import json
import mimetypes
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, ValidationError

from adjacency.contracts import SEVERITY_ACTION, Action, Frozen, InventoryItem
from adjacency.corpus import FrozenCorpus
from adjacency.model_metrics import ModelCallMeasurement, measurement_from_response
from adjacency.xai import ResponseClient, output_text

RAW_PROMPT_SURFACES = {
    1: "model.raw_prompt_baseline.run1",
    2: "model.raw_prompt_baseline.run2",
}


class RawEvidence(Frozen):
    kind: Literal["text", "image"]
    quote: str | None = None
    start: int | None = None
    end: int | None = None
    media_id: str | None = None
    x: int | None = None
    y: int | None = None
    w: int | None = None
    h: int | None = None


class RawPromptVerdict(Frozen):
    item_id: str = Field(min_length=1)
    action: Action
    severity: int = Field(ge=0, le=4)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: tuple[RawEvidence, ...] = ()
    rationale: str = ""


class _RawPromptOutput(Frozen):
    verdicts: tuple[RawPromptVerdict, ...]


@dataclass(frozen=True, slots=True)
class RawPromptRun:
    run_number: int
    verdicts: tuple[RawPromptVerdict, ...]
    raw_output: str
    measurement: ModelCallMeasurement

    def as_dict(self) -> dict[str, object]:
        return {
            "measurement": self.measurement.as_dict(),
            "raw_output": self.raw_output,
            "run_number": self.run_number,
            "verdicts": [verdict.model_dump(mode="json") for verdict in self.verdicts],
        }


class RawPromptError(ValueError):
    """Raised when one raw-prompt run cannot be parsed."""


class RawPromptBaseline:
    """Use policy prose directly, with no compiled policy or structured-output schema."""

    def __init__(
        self,
        client: ResponseClient,
        *,
        media_root: Path | str = ".",
        model: str = "grok-4.5",
    ) -> None:
        self.client = client
        self.media_root = Path(media_root).resolve()
        self.model = model

    def run(
        self,
        corpus: FrozenCorpus,
        *,
        policy_prose: str,
        run_number: int,
    ) -> RawPromptRun:
        if run_number not in RAW_PROMPT_SURFACES:
            raise RawPromptError("run_number must be 1 or 2")
        surface = RAW_PROMPT_SURFACES[run_number]
        payload = self._payload(corpus.items, policy_prose=policy_prose)
        started = time.perf_counter()
        response = self.client.create(surface=surface, payload=payload)
        elapsed_ms = (time.perf_counter() - started) * 1000
        raw = output_text(response)
        try:
            decoded = json.loads(_strip_code_fence(raw))
            parsed = _RawPromptOutput.model_validate(decoded)
        except (json.JSONDecodeError, ValidationError) as error:
            raise RawPromptError("raw-prompt run returned invalid JSON") from error
        measurement = measurement_from_response(
            response,
            surface=surface,
            reasoning_effort="low",
            elapsed_ms=elapsed_ms,
        )
        return RawPromptRun(
            run_number=run_number,
            verdicts=parsed.verdicts,
            raw_output=raw,
            measurement=measurement,
        )

    def _payload(
        self,
        items: Sequence[InventoryItem],
        *,
        policy_prose: str,
    ) -> Mapping[str, Any]:
        instructions = (
            "Apply the advertiser policy directly to every inventory item. Do not create a "
            "PolicySpec. Return JSON only with one top-level key named verdicts. Each verdict must "
            "contain item_id, action, severity, confidence, evidence, and rationale. Action is "
            "ALLOW, REVIEW, or BLOCK. Severity is 0 through 4. Each evidence entry must contain "
            "all of these keys, using null when a field does not apply: kind, quote, start, end, "
            "media_id, x, y, w, h. Text evidence must quote the item exactly with zero-based "
            "character offsets and exclusive end. Image evidence must use a supplied media id and "
            "a box inside its dimensions. Return exactly one verdict for every item id.\n\n"
            f"Advertiser policy:\n{policy_prose}\n\n"
            "Inventory follows."
        )
        content: list[dict[str, Any]] = [{"text": instructions, "type": "input_text"}]
        for item in items:
            content.append(
                {
                    "text": json.dumps(
                        {
                            "item_id": item.item_id,
                            "media": [
                                {
                                    "height": media.height,
                                    "kind": media.kind,
                                    "media_id": media.media_id,
                                    "width": media.width,
                                }
                                for media in item.media
                            ],
                            "text": item.text,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    "type": "input_text",
                }
            )
            for media in item.media:
                if not media.local_path:
                    raise RawPromptError(f"media {media.media_id} has no local path")
                content.append(
                    {
                        "detail": "high",
                        "image_url": self._data_url(media.local_path),
                        "type": "input_image",
                    }
                )
        return {
            "input": [{"content": content, "role": "user"}],
            "max_output_tokens": 16384,
            "model": self.model,
            "reasoning": {"effort": "low"},
            "store": False,
        }

    def _data_url(self, local_path: str) -> str:
        candidate = (self.media_root / local_path).resolve()
        if not candidate.is_relative_to(self.media_root):
            raise RawPromptError(f"media path escapes media root: {local_path}")
        encoded = base64.b64encode(candidate.read_bytes()).decode("ascii")
        mime_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        return f"data:{mime_type};base64,{encoded}"


def compare_raw_prompt_runs(
    corpus: FrozenCorpus,
    first: RawPromptRun,
    second: RawPromptRun,
) -> dict[str, object]:
    expected_ids = {item.item_id for item in corpus.items}
    first_index, first_duplicates = _index(first.verdicts)
    second_index, second_duplicates = _index(second.verdicts)
    shared_ids = sorted(expected_ids & set(first_index) & set(second_index))
    disagreements = [
        item_id
        for item_id in shared_ids
        if first_index[item_id].action is not second_index[item_id].action
    ]
    items = {item.item_id: item for item in corpus.items}
    first_grounding = _grounding_summary(first.verdicts, items)
    second_grounding = _grounding_summary(second.verdicts, items)
    first_coherence = sum(
        SEVERITY_ACTION[verdict.severity] is not verdict.action for verdict in first.verdicts
    )
    second_coherence = sum(
        SEVERITY_ACTION[verdict.severity] is not verdict.action for verdict in second.verdicts
    )
    return {
        "action_disagreement_count": len(disagreements),
        "action_disagreement_item_ids": disagreements,
        "action_disagreement_rate": len(disagreements) / len(shared_ids) if shared_ids else None,
        "corpus_hash": corpus.corpus_hash,
        "expected_item_count": len(expected_ids),
        "run_1": {
            "duplicate_item_ids": first_duplicates,
            "extra_item_ids": sorted(set(first_index) - expected_ids),
            "grounding": first_grounding,
            "missing_item_ids": sorted(expected_ids - set(first_index)),
            "returned_item_count": len(first.verdicts),
            "severity_action_mismatch_count": first_coherence,
        },
        "run_2": {
            "duplicate_item_ids": second_duplicates,
            "extra_item_ids": sorted(set(second_index) - expected_ids),
            "grounding": second_grounding,
            "missing_item_ids": sorted(expected_ids - set(second_index)),
            "returned_item_count": len(second.verdicts),
            "severity_action_mismatch_count": second_coherence,
        },
        "shared_item_count": len(shared_ids),
    }


def _grounding_summary(
    verdicts: Sequence[RawPromptVerdict],
    items: Mapping[str, InventoryItem],
) -> dict[str, object]:
    claims = 0
    failures: list[dict[str, object]] = []
    for verdict in verdicts:
        item = items.get(verdict.item_id)
        for index, evidence in enumerate(verdict.evidence):
            claims += 1
            code = _evidence_failure(evidence, item)
            if code:
                failures.append(
                    {
                        "code": code,
                        "evidence_index": index,
                        "item_id": verdict.item_id,
                    }
                )
    return {
        "claim_count": claims,
        "failure_count": len(failures),
        "failure_rate": len(failures) / claims if claims else None,
        "failures": failures,
    }


def _evidence_failure(evidence: RawEvidence, item: InventoryItem | None) -> str | None:
    if item is None:
        return "ITEM_NOT_FOUND"
    if evidence.kind == "text":
        if (
            evidence.quote is None
            or evidence.start is None
            or evidence.end is None
            or evidence.start < 0
            or evidence.end <= evidence.start
            or evidence.end > len(item.text)
        ):
            return "TEXT_SPAN_MALFORMED"
        if item.text[evidence.start : evidence.end] != evidence.quote:
            return "TEXT_SPAN_NOT_FOUND"
        return None
    if (
        evidence.media_id is None
        or evidence.x is None
        or evidence.y is None
        or evidence.w is None
        or evidence.h is None
    ):
        return "IMAGE_BOX_MALFORMED"
    media = item.media_by_id(evidence.media_id)
    if media is None:
        return "MEDIA_NOT_FOUND"
    if (
        evidence.x < 0
        or evidence.y < 0
        or evidence.w <= 0
        or evidence.h <= 0
        or evidence.x + evidence.w > media.width
        or evidence.y + evidence.h > media.height
    ):
        return "IMAGE_BOX_OUT_OF_BOUNDS"
    return None


def _index(
    verdicts: Sequence[RawPromptVerdict],
) -> tuple[dict[str, RawPromptVerdict], list[str]]:
    index: dict[str, RawPromptVerdict] = {}
    duplicates: list[str] = []
    for verdict in verdicts:
        if verdict.item_id in index:
            duplicates.append(verdict.item_id)
        else:
            index[verdict.item_id] = verdict
    return index, sorted(set(duplicates))


def _strip_code_fence(raw: str) -> str:
    stripped = raw.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        first_newline = stripped.find("\n")
        if first_newline == -1:
            return stripped
        return stripped[first_newline + 1 : -3].strip()
    return stripped
