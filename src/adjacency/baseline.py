"""Auditable keyword-blocklist baseline derived from the advertiser policy."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import Field, ValidationError, field_validator

from adjacency.contracts import Action, Frozen, InventoryItem, PolicySpec, normalize
from adjacency.delta import BaselineDecision
from adjacency.xai import ResponseClient, output_text

KEYWORD_EXPANDER_SURFACE = "model.keyword_expander"
MAX_BLOCKLIST_TERMS = 4_000
_TOKEN_PATTERN = re.compile(r"\w+", flags=re.UNICODE)


def _normalized_tokens(text: str) -> tuple[str, ...]:
    return tuple(_TOKEN_PATTERN.findall(normalize(text).casefold()))


def _normalized_term(text: str) -> str:
    return " ".join(_normalized_tokens(text))


class BaselineBlocklist(Frozen):
    """The conventional baseline, visibly tethered to the compiled policy prose."""

    advertiser: str = Field(min_length=1)
    policy_version: int = Field(ge=1)
    policy_hash: str = Field(min_length=64, max_length=64)
    source_prose: str = Field(min_length=1)
    terms: tuple[str, ...] = Field(min_length=1, max_length=MAX_BLOCKLIST_TERMS)

    @field_validator("source_prose")
    @classmethod
    def _normalize_source_prose(cls, value: str) -> str:
        return normalize(value)

    @field_validator("terms", mode="before")
    @classmethod
    def _normalize_terms(cls, value: object) -> tuple[str, ...]:
        if not isinstance(value, (list, tuple)):
            raise ValueError("terms must be a list or tuple")
        normalized = {_normalized_term(term) for term in value if isinstance(term, str)}
        normalized.discard("")
        return tuple(sorted(normalized))

    @property
    def baseline_hash(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class _KeywordTerms(Frozen):
    terms: tuple[str, ...] = Field(min_length=1, max_length=MAX_BLOCKLIST_TERMS)


class KeywordExpansionError(ValueError):
    """Raised when a model output cannot become the baseline blocklist."""


class KeywordExpander:
    """Expand the exact compiled prose into terms for the comparison baseline."""

    def __init__(self, client: ResponseClient, *, model: str = "grok-4.5") -> None:
        self.client = client
        self.model = model
        self._cache: dict[str, BaselineBlocklist] = {}

    def expand(self, spec: PolicySpec) -> BaselineBlocklist:
        cached = self._cache.get(spec.policy_hash)
        if cached is not None:
            return cached

        response = self.client.create(
            surface=KEYWORD_EXPANDER_SURFACE,
            payload=self._payload(spec),
        )
        try:
            decoded = json.loads(output_text(response))
            expansion = _KeywordTerms.model_validate(decoded)
            blocklist = BaselineBlocklist(
                advertiser=spec.advertiser,
                policy_version=spec.version,
                policy_hash=spec.policy_hash,
                source_prose=spec.prose,
                terms=expansion.terms,
            )
        except (json.JSONDecodeError, ValidationError) as error:
            raise KeywordExpansionError("model returned an invalid keyword expansion") from error

        self._cache[spec.policy_hash] = blocklist
        return blocklist

    def _payload(self, spec: PolicySpec) -> Mapping[str, Any]:
        prompt = (
            "Build a conventional brand-safety keyword blocklist from the advertiser prose "
            "below. Return lowercase terms or short phrases that would trigger blocking. "
            "Include useful lexical variants. Do not include allowance or carve-out language "
            "solely because it appears in the prose. Return at most 4000 unique terms. This "
            "is Arun's comparison baseline, not X's internal blocklist.\n\n"
            f"Advertiser: {spec.advertiser}\n"
            f"Version: {spec.version}\n"
            f"Advertiser prose:\n{spec.prose}"
        )
        return {
            "input": [{"content": prompt, "role": "user"}],
            "max_output_tokens": 8192,
            "model": self.model,
            "reasoning": {"effort": "low"},
            "store": False,
            "text": {
                "format": {
                    "name": "keyword_terms",
                    "schema": _KeywordTerms.model_json_schema(),
                    "strict": True,
                    "type": "json_schema",
                }
            },
        }


class BaselineMatcher:
    """Deterministic whole-token phrase matching over inventory text."""

    def __init__(self, blocklist: BaselineBlocklist) -> None:
        self.blocklist = blocklist
        self._terms = tuple((term, _normalized_tokens(term)) for term in blocklist.terms)

    def match(self, item: InventoryItem) -> BaselineDecision:
        item_tokens = _normalized_tokens(item.text)
        matched = tuple(term for term, tokens in self._terms if self._contains(item_tokens, tokens))
        action = Action.BLOCK if matched else Action.ALLOW
        return BaselineDecision(action=action, matched_terms=matched)

    def match_all(self, items: Iterable[InventoryItem]) -> dict[str, BaselineDecision]:
        decisions: dict[str, BaselineDecision] = {}
        for item in items:
            if item.item_id in decisions:
                raise ValueError(f"duplicate inventory item id: {item.item_id}")
            decisions[item.item_id] = self.match(item)
        return decisions

    @staticmethod
    def _contains(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
        width = len(needle)
        return width > 0 and any(
            haystack[index : index + width] == needle for index in range(len(haystack) - width + 1)
        )
