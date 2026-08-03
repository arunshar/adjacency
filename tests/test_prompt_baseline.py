from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest

from adjacency.contracts import InventoryItem
from adjacency.corpus import FrozenCorpus, FrozenCorpusRecord
from adjacency.prompt_baseline import (
    RawPromptBaseline,
    RawPromptError,
    compare_raw_prompt_runs,
)

pytestmark = pytest.mark.integration


def model_response(verdicts: list[dict[str, object]]) -> dict[str, object]:
    return {
        "id": "raw-response",
        "model": "grok-4.5",
        "output": [
            {
                "content": [
                    {
                        "text": json.dumps({"verdicts": verdicts}),
                        "type": "output_text",
                    }
                ],
                "type": "message",
            }
        ],
        "status": "completed",
        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    }


class StubClient:
    def __init__(self, responses: list[Mapping[str, Any]]) -> None:
        self.responses = responses
        self.payloads: list[Mapping[str, Any]] = []

    def create(self, *, surface: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.payloads.append(payload)
        return self.responses.pop(0)


def raw_verdict(item_id: str, action: str, quote: str, start: int, end: int) -> dict[str, object]:
    return {
        "action": action,
        "confidence": 0.9,
        "evidence": [
            {
                "end": end,
                "h": None,
                "kind": "text",
                "media_id": None,
                "quote": quote,
                "start": start,
                "w": None,
                "x": None,
                "y": None,
            }
        ],
        "item_id": item_id,
        "rationale": "raw prompt",
        "severity": 0 if action == "ALLOW" else 4,
    }


def corpus() -> FrozenCorpus:
    items = (
        InventoryItem(item_id="a", text="Clean weather report."),
        InventoryItem(item_id="b", text="A report about violence."),
    )
    return FrozenCorpus(
        frozen_on="2026-08-03",
        records=tuple(
            FrozenCorpusRecord(
                item=item,
                source_url=f"https://x.com/example/status/{index}",
                source_query="test",
            )
            for index, item in enumerate(items, start=1)
        ),
    )


def test_two_raw_runs_use_identical_payloads_and_measure_disagreement():
    frozen = corpus()
    first_response = model_response(
        [
            raw_verdict("a", "ALLOW", "Clean weather report.", 0, 21),
            raw_verdict("b", "ALLOW", "not present", 0, 11),
        ]
    )
    second_response = model_response(
        [
            raw_verdict("a", "ALLOW", "Clean weather report.", 0, 21),
            raw_verdict("b", "BLOCK", "violence", 15, 23),
        ]
    )
    client = StubClient([first_response, second_response])
    baseline = RawPromptBaseline(client)

    first = baseline.run(frozen, policy_prose="Policy prose", run_number=1)
    second = baseline.run(frozen, policy_prose="Policy prose", run_number=2)
    comparison = compare_raw_prompt_runs(frozen, first, second)

    assert client.payloads[0] == client.payloads[1]
    assert comparison["action_disagreement_count"] == 1
    assert comparison["run_1"]["grounding"]["failure_count"] == 1
    assert comparison["run_2"]["grounding"]["failure_count"] == 0


def test_raw_prompt_invalid_json_is_a_visible_failure():
    invalid = {
        "output": [{"content": [{"text": "not json", "type": "output_text"}], "type": "message"}],
        "status": "completed",
    }
    with pytest.raises(RawPromptError, match="invalid JSON"):
        RawPromptBaseline(StubClient([invalid])).run(
            corpus(), policy_prose="Policy prose", run_number=1
        )
