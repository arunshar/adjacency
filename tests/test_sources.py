from __future__ import annotations

import pytest

from adjacency.sources import (
    SOURCE_SPECS,
    Source,
    SourceConfigurationError,
    require_eval_source,
    require_source_credentials,
    selected_source,
)


def test_all_four_sources_are_fixed_and_frozen_corpus_is_default():
    assert set(SOURCE_SPECS) == set(Source)
    assert selected_source({}) is Source.FROZEN_CORPUS
    assert selected_source({"ADJ_SOURCE": "grok_x_search"}) is Source.GROK_X_SEARCH
    assert selected_source({"ADJ_SOURCE": "live_x_api"}) is Source.LIVE_X_API
    assert selected_source({"ADJ_SOURCE": "synthetic_faults"}) is Source.SYNTHETIC_FAULTS


def test_live_sources_require_credentials_and_cannot_back_eval_numbers():
    with pytest.raises(SourceConfigurationError, match="XAI_API_KEY"):
        require_source_credentials(Source.GROK_X_SEARCH, {})
    assert require_source_credentials(
        Source.GROK_X_SEARCH, {"XAI_API_KEY": "present"}
    ).network_required
    with pytest.raises(SourceConfigurationError, match="not valid for eval numbers"):
        require_eval_source(Source.LIVE_X_API)
    assert require_eval_source(Source.FROZEN_CORPUS).valid_for_eval_numbers
    assert require_eval_source(Source.SYNTHETIC_FAULTS).valid_for_eval_numbers


def test_unknown_source_fails_with_all_legal_choices():
    with pytest.raises(SourceConfigurationError, match="grok_x_search"):
        selected_source({"ADJ_SOURCE": "improvised_friday_source"})
