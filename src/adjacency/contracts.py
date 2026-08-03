"""Frozen data contracts for the Adjacency policy engine.

These four types are the interface between every stage of the pipeline. They are
defined once, here, and nothing downstream is permitted to widen them.

The invariant that matters, and the one worth stating out loud: **the rationale is
display-only.** A verdict's decision is computed from `action`, `severity`,
`clause_ids`, and `evidence`, all of which a gate can check mechanically. The prose
rationale is rendered to a human and is never read by a gate. A model that writes a
persuasive paragraph cannot argue its way past a lookup table.

Text offsets
------------
Spans are **character offsets into the NFC-normalized text**, not byte offsets and not
UTF-16 code units. This is a deliberate choice and it is load-bearing on a platform
whose posts are full of emoji, combining marks, and mixed scripts.

Three encodings disagree about the length of the same string. The family emoji, a
zero-width-joiner sequence of man, woman, girl, and boy, is 1 grapheme, 7 Python
characters, 25 UTF-8 bytes, and 11 UTF-16 code units. A model asked for "the byte
offset" will not reliably give you any one of those. So Adjacency normalizes to NFC on
ingest, indexes in Python
characters, and re-derives the span by exact string equality rather than trusting the
model's arithmetic. `Evidence.quote` is the source of truth; the offsets are a claim
about where it appears, and G1 checks that claim rather than assuming it.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Action(StrEnum):
    """What the engine decides to do with a piece of inventory."""

    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REVIEW = "REVIEW"


class DeltaKind(StrEnum):
    """How the engine's decision compares to the keyword-blocklist baseline."""

    AGREE = "AGREE"
    OVER_BLOCK = "OVER_BLOCK"
    """The baseline withholds it and the engine serves it."""
    UNDER_BLOCK = "UNDER_BLOCK"
    """The baseline serves it and the engine withholds it."""


#: Severity to action. A verdict whose `action` disagrees with this table is incoherent
#: and G4 rejects it. Frozen deliberately: the model does not get to argue with a dict.
SEVERITY_ACTION: dict[int, Action] = {
    0: Action.ALLOW,
    1: Action.ALLOW,
    2: Action.REVIEW,
    3: Action.BLOCK,
    4: Action.BLOCK,
}

MIN_SEVERITY = 0
MAX_SEVERITY = 4


def normalize(text: str) -> str:
    """NFC-normalize so that offsets computed here mean the same thing everywhere."""
    return unicodedata.normalize("NFC", text)


def _stable_hash(payload: object) -> str:
    """Content hash used for `policy_hash` and `corpus_hash`.

    Sorted keys and a compact separator so that a semantically identical object hashes
    identically regardless of construction order. This is half of the reproducibility
    claim: the tuple (policy_hash, corpus_hash, model, reasoning_effort, seed) has to
    determine a run, which is only true if the hashes are stable.
    """
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class Frozen(BaseModel):
    """Base for every contract: immutable, no undeclared fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")


# --------------------------------------------------------------------------------------
# 1. PolicySpec: the compiled artifact
# --------------------------------------------------------------------------------------


class Clause(Frozen):
    """One rule, compiled from a span of the advertiser's own prose.

    `source_start` and `source_end` point back into the prose the advertiser wrote.
    G0 checks that `prose[source_start:source_end] == source_text` exactly. A clause
    that cannot point at the sentence it came from is a clause the model invented.
    """

    clause_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    severity: int = Field(ge=MIN_SEVERITY, le=MAX_SEVERITY)
    description: str = Field(min_length=1)
    source_text: str = Field(min_length=1)
    source_start: int = Field(ge=0)
    source_end: int = Field(ge=0)

    @model_validator(mode="after")
    def _span_is_ordered(self) -> Clause:
        if self.source_end <= self.source_start:
            raise ValueError(
                f"clause {self.clause_id}: source_end ({self.source_end}) must exceed "
                f"source_start ({self.source_start})"
            )
        if self.source_end - self.source_start != len(self.source_text):
            raise ValueError(
                f"clause {self.clause_id}: span width "
                f"{self.source_end - self.source_start} does not match source_text length "
                f"{len(self.source_text)}"
            )
        return self


class PolicySpec(Frozen):
    """An advertiser's brand-safety policy, compiled from prose into checkable structure.

    Hashed and versioned so that two runs of the same policy are provably the same
    policy, and so that a revision produces a diff rather than an opaque replacement.
    """

    version: int = Field(ge=1)
    advertiser: str = Field(min_length=1)
    prose: str = Field(min_length=1)
    clauses: tuple[Clause, ...]

    @field_validator("prose")
    @classmethod
    def _normalize_prose(cls, v: str) -> str:
        return normalize(v)

    @model_validator(mode="after")
    def _clause_ids_unique(self) -> PolicySpec:
        seen = [c.clause_id for c in self.clauses]
        dupes = {c for c in seen if seen.count(c) > 1}
        if dupes:
            raise ValueError(f"duplicate clause_id(s): {sorted(dupes)}")
        return self

    @property
    def policy_hash(self) -> str:
        return _stable_hash(
            {
                "version": self.version,
                "advertiser": self.advertiser,
                "prose": self.prose,
                "clauses": [c.model_dump() for c in self.clauses],
            }
        )

    def clause(self, clause_id: str) -> Clause | None:
        for c in self.clauses:
            if c.clause_id == clause_id:
                return c
        return None

    @property
    def clause_ids(self) -> frozenset[str]:
        return frozenset(c.clause_id for c in self.clauses)


# --------------------------------------------------------------------------------------
# 2. InventoryItem: a piece of ad-adjacent content
# --------------------------------------------------------------------------------------


class Media(Frozen):
    """An image or video attached to a post.

    `width` and `height` are required because G1 uses them to check that a cited
    bounding box actually lies inside the frame. Evidence pointing outside the image
    is evidence about an image that does not exist.
    """

    media_id: str = Field(min_length=1)
    kind: Literal["image", "video"]
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    local_path: str | None = None
    url: str | None = None


class InventoryItem(Frozen):
    """One unit of inventory an ad could be placed next to."""

    item_id: str = Field(min_length=1)
    text: str = ""
    media: tuple[Media, ...] = ()
    author_handle: str | None = None
    created_at: str | None = None

    @field_validator("text")
    @classmethod
    def _normalize_text(cls, v: str) -> str:
        return normalize(v)

    @property
    def has_media(self) -> bool:
        return len(self.media) > 0

    def media_by_id(self, media_id: str) -> Media | None:
        for m in self.media:
            if m.media_id == media_id:
                return m
        return None


# --------------------------------------------------------------------------------------
# 3. Verdict: what the engine decided, and why, checkably
# --------------------------------------------------------------------------------------


class TextEvidence(Frozen):
    """A claim that `quote` appears at [start, end) in the item's text."""

    kind: Literal["text"] = "text"
    quote: str = Field(min_length=1)
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class ImageEvidence(Frozen):
    """A claim about a region of a specific piece of media.

    Box is (x, y, w, h) in pixels, origin top-left.
    """

    kind: Literal["image"] = "image"
    media_id: str = Field(min_length=1)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    w: int = Field(gt=0)
    h: int = Field(gt=0)
    note: str = ""


Evidence = TextEvidence | ImageEvidence


class Verdict(Frozen):
    """The engine's decision on one item.

    `rationale` is rendered to humans and read by no gate. Everything a gate checks is
    a structured field.
    """

    item_id: str = Field(min_length=1)
    action: Action
    severity: int = Field(ge=MIN_SEVERITY, le=MAX_SEVERITY)
    clause_ids: tuple[str, ...] = ()
    evidence: tuple[TextEvidence | ImageEvidence, ...] = ()
    confidence: float = Field(ge=0.0, le=1.0)
    tier: Literal[0, 1, 2] = 0
    """0 = decided deterministically at no model cost, 1 = low effort, 2 = escalated."""
    rationale: str = ""
    """Display only. Never read by a gate."""
    policy_version: int = Field(ge=1)

    def coerced_to(self, action: Action, *, reason: str) -> Verdict:
        """Return a copy forced to `action`, with the reason appended to the rationale.

        Gates fail closed by coercing rather than mutating, so the original verdict
        stays intact in the audit ledger next to the coercion that overrode it.
        """
        note = f"[coerced to {action.value}: {reason}]"
        return self.model_copy(
            update={
                "action": action,
                "rationale": f"{self.rationale} {note}".strip(),
            }
        )


# --------------------------------------------------------------------------------------
# 4. DeltaRow: engine versus keyword blocklist
# --------------------------------------------------------------------------------------


class DeltaRow(Frozen):
    """How the engine's decision compares to what the blocklist would have done."""

    item_id: str = Field(min_length=1)
    engine_action: Action
    baseline_action: Action
    matched_terms: tuple[str, ...] = ()
    """Blocklist terms that fired on this item. Empty when the baseline allowed it."""

    @property
    def kind(self) -> DeltaKind:
        engine_withholds = self.engine_action is not Action.ALLOW
        baseline_withholds = self.baseline_action is not Action.ALLOW
        if engine_withholds == baseline_withholds:
            return DeltaKind.AGREE
        if baseline_withholds and not engine_withholds:
            return DeltaKind.OVER_BLOCK
        return DeltaKind.UNDER_BLOCK
