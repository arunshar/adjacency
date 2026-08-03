"""Recorded access to the xAI Responses API.

Every request goes through :class:`FixtureStore`. Replay is the default, so tests
and demos remain offline unless ``ADJ_RECORD=1`` is set intentionally.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any, Protocol, cast

from adjacency.fixtures import FixtureStore

XAI_RESPONSES_URL = "https://api.x.ai/v1/responses"


class XAIResponseError(RuntimeError):
    """Raised when xAI transport or response parsing fails."""


class ResponseClient(Protocol):
    """Small interface used by model-backed pipeline stages."""

    def create(self, *, surface: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """Create or replay one response."""


Transport = Callable[[Mapping[str, Any]], Mapping[str, Any]]


class RecordedXAIClient:
    """Raw xAI Responses client with content-addressed record and replay."""

    def __init__(
        self,
        fixture_store: FixtureStore | None = None,
        *,
        transport: Transport | None = None,
        timeout_s: float = 120.0,
    ) -> None:
        self.fixture_store = fixture_store or FixtureStore()
        self._transport = transport or self._post
        self.timeout_s = timeout_s

    def create(self, *, surface: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        response = self.fixture_store.call(
            surface,
            payload,
            lambda: self._transport(payload),
        )
        if not isinstance(response, Mapping):
            raise XAIResponseError("Responses API payload must be a JSON object")
        return cast(Mapping[str, Any], response)

    def _post(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        api_key = os.environ.get("XAI_API_KEY")
        if not api_key:
            raise XAIResponseError("XAI_API_KEY is required only when ADJ_RECORD=1")

        request = urllib.request.Request(
            XAI_RESPONSES_URL,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            # The request URL is the fixed HTTPS endpoint above.
            with urllib.request.urlopen(  # nosec B310
                request,
                timeout=self.timeout_s,
            ) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as error:
            raise XAIResponseError(f"xAI Responses API returned HTTP {error.code}") from error
        except urllib.error.URLError as error:
            raise XAIResponseError("xAI Responses API transport failed") from error

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as error:
            raise XAIResponseError("xAI Responses API returned invalid JSON") from error
        if not isinstance(parsed, Mapping):
            raise XAIResponseError("xAI Responses API returned a non-object response")
        return cast(Mapping[str, Any], parsed)


def output_text(response: Mapping[str, Any]) -> str:
    """Extract the single structured-output text body from a Responses object."""

    if response.get("status") not in (None, "completed"):
        raise XAIResponseError(f"Responses API status is {response.get('status')!r}")

    texts: list[str] = []
    output = response.get("output")
    if not isinstance(output, list):
        raise XAIResponseError("Responses API output is missing")
    for item in output:
        if not isinstance(item, Mapping) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if (
                isinstance(part, Mapping)
                and part.get("type") == "output_text"
                and isinstance(part.get("text"), str)
            ):
                texts.append(cast(str, part["text"]))
    if len(texts) != 1:
        raise XAIResponseError(f"expected one output_text part, received {len(texts)}")
    return texts[0]
