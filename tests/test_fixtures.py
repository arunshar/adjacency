from __future__ import annotations

import json

import pytest

from adjacency.fixtures import FixtureMissError, FixtureSecretError, FixtureStore


def test_record_then_replay_is_content_addressed_and_offline(tmp_path):
    request = {
        "input": [{"content": "Classify this item", "role": "user"}],
        "model": "grok-4.5",
    }
    live_calls = []
    recorder = FixtureStore(tmp_path, record=True)

    recorded = recorder.call(
        "model.judge",
        request,
        lambda: live_calls.append("called") or {"action": "ALLOW", "confidence": 0.98},
    )

    assert recorded == {"action": "ALLOW", "confidence": 0.98}
    assert live_calls == ["called"]
    fixture_path = recorder.fixture_path("model.judge", request)
    assert fixture_path.is_file()
    document = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert document["request_sha256"] == fixture_path.stem

    replay = FixtureStore(tmp_path, record=False)
    replayed = replay.call(
        "model.judge",
        {"model": "grok-4.5", "input": request["input"]},
        lambda: pytest.fail("replay attempted a live call"),
    )
    assert replayed == recorded


def test_replay_fails_closed_when_fixture_is_missing(tmp_path):
    store = FixtureStore(tmp_path, record=False)

    with pytest.raises(FixtureMissError, match="ADJ_RECORD=1"):
        store.call("tool.x_search", {"query": "brand safety"})


def test_recorder_rejects_credentials_before_invocation(tmp_path):
    store = FixtureStore(tmp_path, record=True)

    with pytest.raises(FixtureSecretError, match="credential field"):
        store.call(
            "model.judge",
            {"api_key": "not-written"},
            lambda: pytest.fail("credential validation happened too late"),
        )
