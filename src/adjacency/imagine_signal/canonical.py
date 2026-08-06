"""Public canonical JSON and content hashing for ImagineSignal.

The existing Adjacency package keeps its hashing helper private. ImagineSignal uses
this parallel implementation so its contracts can evolve without changing existing
hash vectors. The representation is deliberately small: valid JSON values, Pydantic
models, enums, dates, datetimes, tuples, and sets.
"""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from collections.abc import Mapping, Sequence, Set
from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


def normalize_text(value: str) -> str:
    """Return the NFC representation used by hashes and string contracts."""

    return unicodedata.normalize("NFC", value)


def _canonical_value(value: object) -> object:
    if isinstance(value, BaseModel):
        return _canonical_value(value.model_dump(mode="json"))
    if isinstance(value, Enum):
        return _canonical_value(value.value)
    if isinstance(value, datetime):
        rendered = value.isoformat()
        return f"{rendered[:-6]}Z" if rendered.endswith("+00:00") else rendered
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return normalize_text(value)
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("canonical JSON rejects non-finite floats")
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("canonical JSON object keys must be strings")
            canonical_key = normalize_text(key)
            if canonical_key in normalized:
                raise ValueError("canonical JSON keys collide after NFC normalization")
            normalized[canonical_key] = _canonical_value(item)
        return normalized
    if isinstance(value, Set):
        members = [_canonical_value(item) for item in value]
        return sorted(members, key=canonical_json)
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        return [_canonical_value(item) for item in value]
    if isinstance(value, bytes | bytearray):
        raise TypeError("binary data must be stored by digest, not inside canonical JSON")
    raise TypeError(f"unsupported canonical JSON type: {type(value).__name__}")


def canonical_json(value: object) -> str:
    """Serialize a value to deterministic, compact, UTF-8-safe JSON text."""

    return json.dumps(
        _canonical_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_json_bytes(value: object) -> bytes:
    """Return the exact UTF-8 bytes used for content addressing."""

    return canonical_json(value).encode("utf-8")


def content_sha256(value: object) -> str:
    """Return the lower-case SHA-256 digest of a canonical value."""

    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def canonical_payload(value: object) -> Any:
    """Expose the normalized JSON-compatible value for artifact writers."""

    return _canonical_value(value)
