from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest

from adjacency.policy import POLICY_COMPILER_SURFACE, PolicyCompileError, PolicyCompiler

pytestmark = pytest.mark.unit


def response_for(payload: Mapping[str, Any]) -> dict[str, object]:
    return {
        "output": [
            {
                "content": [
                    {
                        "text": json.dumps(payload),
                        "type": "output_text",
                    }
                ],
                "type": "message",
            }
        ],
        "status": "completed",
    }


class StubClient:
    def __init__(self, response: Mapping[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[str, Mapping[str, Any]]] = []

    def create(self, *, surface: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.calls.append((surface, payload))
        return self.response


def test_compiler_runs_high_reasoning_once_then_returns_cached_g0_policy():
    prose = "Block illegal drug sales."
    client = StubClient(
        response_for(
            {
                "advertiser": "Northstar",
                "clauses": [
                    {
                        "category": "illegal_drugs",
                        "clause_id": "C1",
                        "description": "Block illegal drug sales",
                        "severity": 4,
                        "source_end": len(prose),
                        "source_start": 0,
                        "source_text": prose,
                    }
                ],
                "prose": prose,
                "version": 1,
            }
        )
    )
    compiler = PolicyCompiler(client)

    first = compiler.compile(advertiser="Northstar", prose=prose)
    second = compiler.compile(advertiser="Northstar", prose=prose)

    assert first is second
    assert len(client.calls) == 1
    surface, request = client.calls[0]
    assert surface == POLICY_COMPILER_SURFACE
    assert request["reasoning"] == {"effort": "high"}
    assert request["text"]["format"]["strict"] is True


def test_compiler_rejects_model_clause_that_fails_g0():
    prose = "Block cats"
    client = StubClient(
        response_for(
            {
                "advertiser": "Northstar",
                "clauses": [
                    {
                        "category": "animals",
                        "clause_id": "C1",
                        "description": "Invented allowance",
                        "severity": 1,
                        "source_end": len(prose),
                        "source_start": 0,
                        "source_text": "Allow cats",
                    }
                ],
                "prose": prose,
                "version": 1,
            }
        )
    )

    with pytest.raises(PolicyCompileError, match="G0_SPAN_MISMATCH"):
        PolicyCompiler(client).compile(advertiser="Northstar", prose=prose)


@pytest.mark.parametrize(
    ("field", "changed", "message"),
    (
        ("advertiser", "Different", "trusted advertiser"),
        ("prose", "Allow cats", "trusted advertiser prose"),
        ("version", 2, "trusted policy version"),
    ),
)
def test_compiler_rejects_a_rewritten_trusted_input(field, changed, message):
    compiled = {
        "advertiser": "Northstar",
        "clauses": [
            {
                "category": "animals",
                "clause_id": "C1",
                "description": "Rule about cats",
                "severity": 4,
                "source_end": 10,
                "source_start": 0,
                "source_text": "Block cats",
            }
        ],
        "prose": "Block cats",
        "version": 1,
    }
    compiled[field] = changed
    if field == "prose":
        compiled["clauses"][0]["severity"] = 1
        compiled["clauses"][0]["source_text"] = changed
    client = StubClient(response_for(compiled))

    with pytest.raises(PolicyCompileError, match=message):
        PolicyCompiler(client).compile(advertiser="Northstar", prose="Block cats")
