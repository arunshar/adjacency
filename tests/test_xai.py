from __future__ import annotations

import pytest

from adjacency.fixtures import FixtureStore
from adjacency.xai import RecordedXAIClient, XAIResponseError, output_text

pytestmark = pytest.mark.integration


def response_with_text(text: str) -> dict[str, object]:
    return {
        "output": [
            {
                "content": [{"text": text, "type": "output_text"}],
                "role": "assistant",
                "type": "message",
            }
        ],
        "status": "completed",
    }


def test_recorded_client_replays_without_invoking_transport(tmp_path):
    payload = {"input": "hello", "model": "grok-4.5"}
    live_calls: list[object] = []
    recorder = RecordedXAIClient(
        FixtureStore(tmp_path, record=True),
        transport=lambda request: live_calls.append(request) or response_with_text("ok"),
    )

    recorded = recorder.create(surface="model.test", payload=payload)
    replay = RecordedXAIClient(
        FixtureStore(tmp_path, record=False),
        transport=lambda _request: pytest.fail("replay invoked transport"),
    )

    assert output_text(recorded) == "ok"
    assert output_text(replay.create(surface="model.test", payload=payload)) == "ok"
    assert live_calls == [payload]


def test_record_mode_without_key_fails_before_network(tmp_path, monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    client = RecordedXAIClient(FixtureStore(tmp_path, record=True))

    with pytest.raises(XAIResponseError, match="XAI_API_KEY"):
        client.create(surface="model.test", payload={"input": "hello"})


def test_output_text_rejects_incomplete_or_ambiguous_responses():
    with pytest.raises(XAIResponseError, match="status"):
        output_text({"output": [], "status": "failed"})

    duplicated = response_with_text("one")
    duplicated["output"].append(duplicated["output"][0])
    with pytest.raises(XAIResponseError, match="received 2"):
        output_text(duplicated)
