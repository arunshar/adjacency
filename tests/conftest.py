"""Shared fixtures and hermeticity guard.

Unit tests may not reach the network. The guard blocks name resolution and outbound
connect rather than the socket constructor, so asyncio's self-pipe still works.
"""

from __future__ import annotations

import socket

import pytest

from adjacency.contracts import (
    Action,
    Clause,
    ImageEvidence,
    InventoryItem,
    Media,
    PolicySpec,
    TextEvidence,
    Verdict,
)

PROSE = (
    "Do not place our ads next to depictions of aviation accidents. "
    "Avoid content celebrating violence. "
    "We are comfortable with ordinary news reporting."
)


def pytest_configure(config):
    for marker in ("unit", "integration", "smoke", "e2e", "slow"):
        config.addinivalue_line("markers", marker)


@pytest.fixture(autouse=True)
def _no_network_in_unit(request, monkeypatch):
    if request.node.get_closest_marker("unit") is None:
        return

    def _blocked(*_a, **_k):
        raise RuntimeError("network blocked in @pytest.mark.unit test")

    monkeypatch.setattr(socket, "getaddrinfo", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)


def clause_from_prose(
    clause_id: str, needle: str, *, severity: int, category: str = "safety"
) -> Clause:
    """Build a clause whose span is derived from the prose, so G0 passes by construction."""
    start = PROSE.index(needle)
    return Clause(
        clause_id=clause_id,
        category=category,
        severity=severity,
        description=f"rule from {needle!r}",
        source_text=needle,
        source_start=start,
        source_end=start + len(needle),
    )


@pytest.fixture
def spec() -> PolicySpec:
    return PolicySpec(
        version=1,
        advertiser="TestAir",
        prose=PROSE,
        clauses=(
            clause_from_prose("C1", "depictions of aviation accidents", severity=4),
            clause_from_prose("C2", "content celebrating violence", severity=3),
        ),
    )


@pytest.fixture
def item() -> InventoryItem:
    return InventoryItem(
        item_id="post-1",
        text="Breaking: an aviation accident at the airfield this morning.",
        media=(Media(media_id="m1", kind="image", width=1200, height=800),),
        author_handle="newswire",
    )


@pytest.fixture
def clean_item() -> InventoryItem:
    return InventoryItem(item_id="post-2", text="Great weather for flying today.")


def make_verdict(
    item_id: str = "post-1",
    *,
    action: Action = Action.BLOCK,
    severity: int = 3,
    clause_ids: tuple[str, ...] = ("C2",),
    evidence: tuple[TextEvidence | ImageEvidence, ...] = (),
    confidence: float = 0.9,
    tier: int = 1,
    policy_version: int = 1,
) -> Verdict:
    return Verdict(
        item_id=item_id,
        action=action,
        severity=severity,
        clause_ids=clause_ids,
        evidence=evidence,
        confidence=confidence,
        tier=tier,
        rationale="test rationale",
        policy_version=policy_version,
    )


def text_evidence_for(item: InventoryItem, needle: str) -> TextEvidence:
    """Evidence that is correct by construction, for the happy path."""
    start = item.text.index(needle)
    return TextEvidence(quote=needle, start=start, end=start + len(needle))
