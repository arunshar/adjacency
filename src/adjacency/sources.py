"""The fixed inventory-source switch for the build and the demo.

Evaluation always defaults to the frozen corpus. Live sources are explicit opt-in
choices. Synthetic faults stay available even when every credential and network
path is unavailable.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class Source(StrEnum):
    GROK_X_SEARCH = "grok_x_search"
    LIVE_X_API = "live_x_api"
    FROZEN_CORPUS = "frozen_corpus"
    SYNTHETIC_FAULTS = "synthetic_faults"


@dataclass(frozen=True, slots=True)
class SourceSpec:
    source: Source
    network_required: bool
    credential_names: tuple[str, ...]
    valid_for_eval_numbers: bool


SOURCE_SPECS = {
    Source.GROK_X_SEARCH: SourceSpec(
        source=Source.GROK_X_SEARCH,
        network_required=True,
        credential_names=("XAI_API_KEY",),
        valid_for_eval_numbers=False,
    ),
    Source.LIVE_X_API: SourceSpec(
        source=Source.LIVE_X_API,
        network_required=True,
        credential_names=("X_BEARER_TOKEN",),
        valid_for_eval_numbers=False,
    ),
    Source.FROZEN_CORPUS: SourceSpec(
        source=Source.FROZEN_CORPUS,
        network_required=False,
        credential_names=(),
        valid_for_eval_numbers=True,
    ),
    Source.SYNTHETIC_FAULTS: SourceSpec(
        source=Source.SYNTHETIC_FAULTS,
        network_required=False,
        credential_names=(),
        valid_for_eval_numbers=True,
    ),
}


class SourceConfigurationError(ValueError):
    """Raised when the selected source is unknown or lacks required credentials."""


def selected_source(environ: Mapping[str, str] | None = None) -> Source:
    values = os.environ if environ is None else environ
    raw = values.get("ADJ_SOURCE", Source.FROZEN_CORPUS.value)
    try:
        return Source(raw)
    except ValueError as error:
        choices = ", ".join(source.value for source in Source)
        raise SourceConfigurationError(
            f"unknown ADJ_SOURCE {raw!r}. Choose one of: {choices}"
        ) from error


def source_spec(source: Source | str | None = None) -> SourceSpec:
    selected = selected_source() if source is None else Source(source)
    return SOURCE_SPECS[selected]


def require_source_credentials(
    source: Source | str | None = None,
    environ: Mapping[str, str] | None = None,
) -> SourceSpec:
    values = os.environ if environ is None else environ
    spec = source_spec(source)
    missing = [name for name in spec.credential_names if not values.get(name)]
    if missing:
        names = ", ".join(missing)
        raise SourceConfigurationError(f"{spec.source.value} requires: {names}")
    return spec


def require_eval_source(source: Source | str | None = None) -> SourceSpec:
    spec = source_spec(source)
    if not spec.valid_for_eval_numbers:
        raise SourceConfigurationError(
            f"{spec.source.value} is not valid for eval numbers. Use frozen_corpus or "
            "synthetic_faults."
        )
    return spec
