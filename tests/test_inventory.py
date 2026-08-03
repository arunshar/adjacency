from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest

from adjacency.fixtures import FixtureStore
from adjacency.inventory import (
    FetchResult,
    InventoryFetcher,
    InventoryFetchError,
    InventorySearch,
    XStatusResolver,
)

pytestmark = pytest.mark.integration


def response_with_posts(posts: list[dict[str, object]]) -> dict[str, object]:
    return {
        "id": "inventory-response",
        "model": "grok-4.5",
        "output": [
            {
                "content": [{"text": json.dumps({"posts": posts}), "type": "output_text"}],
                "type": "message",
            }
        ],
        "status": "completed",
        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    }


class StubClient:
    def __init__(self, response: Mapping[str, Any]) -> None:
        self.response = response
        self.payload: Mapping[str, Any] | None = None

    def create(self, *, surface: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        self.payload = payload
        return self.response


def post(url: str = "https://x.com/example/status/123") -> dict[str, object]:
    return {
        "author_handle": "@example",
        "created_at": "2026-08-01",
        "has_media": True,
        "source_url": url,
        "text": "A public post.",
    }


def test_inventory_fetcher_uses_x_search_and_normalizes_status_urls():
    client = StubClient(response_with_posts([post("https://twitter.com/example/status/123")]))
    search = InventorySearch(
        label="news",
        query="neutral reporting",
        from_date="2026-07-01",
        to_date="2026-08-02",
    )

    result: FetchResult = InventoryFetcher(client).fetch(search)

    assert result.posts[0].source_url == "https://x.com/example/status/123"
    assert client.payload is not None
    assert client.payload["tools"][0]["type"] == "x_search"
    assert client.payload["text"]["format"]["strict"] is True


def test_inventory_fetcher_rejects_an_invalid_model_batch():
    client = StubClient(response_with_posts([post("https://example.com/not-x")]))
    search = InventorySearch("bad", "bad", "2026-07-01", "2026-08-02")

    with pytest.raises(InventoryFetchError, match="invalid inventory batch"):
        InventoryFetcher(client).fetch(search)


def test_status_metadata_records_then_replays_without_transport(tmp_path):
    source_url = "https://x.com/example/status/123"
    details = {
        "author_handle": "@example",
        "created_at": "August 1, 2026",
        "media_height": 400,
        "media_url": "https://pbs.twimg.com/media/example.jpg",
        "media_width": 600,
        "source_url": source_url,
        "text": "Verified exact post text.",
    }
    recorder = XStatusResolver(
        FixtureStore(tmp_path, record=True),
        transport=lambda _url: details,
    )
    assert recorder.resolve(source_url).text == details["text"]

    replay = XStatusResolver(
        FixtureStore(tmp_path, record=False),
        transport=lambda _url: pytest.fail("replay invoked metadata transport"),
    )
    assert replay.resolve(source_url).media_width == 600
