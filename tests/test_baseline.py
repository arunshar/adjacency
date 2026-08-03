from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest
from pydantic import ValidationError

from adjacency.baseline import (
    MAX_BLOCKLIST_TERMS,
    BaselineBlocklist,
    BaselineMatcher,
    KeywordExpander,
)
from adjacency.contracts import Action, InventoryItem

pytestmark = pytest.mark.unit


def response_for(terms: list[str]) -> dict[str, object]:
    return {
        "output": [
            {
                "content": [
                    {
                        "text": json.dumps({"terms": terms}),
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
        self.calls: list[Mapping[str, Any]] = []

    def create(self, *, surface: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.calls.append({"payload": payload, "surface": surface})
        return self.response


def test_expander_uses_the_compiled_prose_and_caches_by_policy_hash(spec):
    client = StubClient(response_for(["Violence", "drug-sales", "violence"]))
    expander = KeywordExpander(client)

    first = expander.expand(spec)
    second = expander.expand(spec)

    assert first is second
    assert len(client.calls) == 1
    assert first.source_prose == spec.prose
    assert first.policy_hash == spec.policy_hash
    assert first.terms == ("drug sales", "violence")
    assert spec.prose in client.calls[0]["payload"]["input"][0]["content"]


def test_blocklist_enforces_the_term_cap(spec):
    with pytest.raises(ValidationError, match="at most 4000 items"):
        BaselineBlocklist(
            advertiser=spec.advertiser,
            policy_version=spec.version,
            policy_hash=spec.policy_hash,
            source_prose=spec.prose,
            terms=tuple(f"term {index}" for index in range(MAX_BLOCKLIST_TERMS + 1)),
        )


def test_matcher_is_deterministic_and_uses_whole_token_phrases(spec):
    blocklist = BaselineBlocklist(
        advertiser=spec.advertiser,
        policy_version=spec.version,
        policy_hash=spec.policy_hash,
        source_prose=spec.prose,
        terms=("gun", "illegal drug sales"),
    )
    matcher = BaselineMatcher(blocklist)
    decisions = matcher.match_all(
        (
            InventoryItem(item_id="phrase", text="Report on ILLEGAL drug-sales nearby."),
            InventoryItem(item_id="substring", text="The race has begun."),
        )
    )

    assert decisions["phrase"].action is Action.BLOCK
    assert decisions["phrase"].matched_terms == ("illegal drug sales",)
    assert decisions["substring"].action is Action.ALLOW

    with pytest.raises(ValueError, match="duplicate inventory"):
        matcher.match_all(
            (
                InventoryItem(item_id="same", text="gun"),
                InventoryItem(item_id="same", text="clean"),
            )
        )
