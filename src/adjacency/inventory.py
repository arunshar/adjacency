"""Inventory discovery over x_search with recorded source verification."""

from __future__ import annotations

import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, cast

from pydantic import Field, ValidationError, field_validator

from adjacency.contracts import Frozen, normalize
from adjacency.fixtures import FixtureStore
from adjacency.model_metrics import ModelCallMeasurement, measurement_from_response
from adjacency.xai import ResponseClient, output_text

INVENTORY_FETCH_SURFACE = "tool.x_search.inventory"
STATUS_METADATA_SURFACE = "http.x_status_metadata"
_STATUS_URL = re.compile(r"https://(?:x|twitter)\.com/([A-Za-z0-9_]+)/status/(\d+)(?:\?.*)?\Z")


def _canonical_status_url(value: str) -> str:
    match = _STATUS_URL.fullmatch(value)
    if not match:
        raise ValueError("source_url must be a direct X status URL")
    return f"https://x.com/{match.group(1)}/status/{match.group(2)}"


class XSearchPost(Frozen):
    source_url: str
    text: str = Field(min_length=1)
    author_handle: str = Field(min_length=1)
    created_at: str = Field(min_length=1)
    has_media: bool

    @field_validator("source_url")
    @classmethod
    def _direct_status_url(cls, value: str) -> str:
        return _canonical_status_url(value)

    @field_validator("text")
    @classmethod
    def _normalize_text(cls, value: str) -> str:
        return normalize(value).strip()


class _XSearchBatch(Frozen):
    posts: tuple[XSearchPost, ...] = Field(min_length=1, max_length=20)


@dataclass(frozen=True, slots=True)
class InventorySearch:
    label: str
    query: str
    from_date: str
    to_date: str
    limit: int = 12
    allowed_x_handles: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FetchResult:
    search: InventorySearch
    posts: tuple[XSearchPost, ...]
    measurement: ModelCallMeasurement


class InventoryFetchError(ValueError):
    """Raised when x_search does not produce a usable inventory batch."""


class InventoryFetcher:
    """Discover direct X status URLs through the recorded x_search surface."""

    def __init__(self, client: ResponseClient, *, model: str = "grok-4.5") -> None:
        self.client = client
        self.model = model

    def fetch(self, search: InventorySearch) -> FetchResult:
        if not search.label.strip() or not search.query.strip():
            raise InventoryFetchError("search label and query cannot be blank")
        if not 1 <= search.limit <= 20:
            raise InventoryFetchError("search limit must be between 1 and 20")
        payload = self._payload(search)
        started = time.perf_counter()
        response = self.client.create(surface=INVENTORY_FETCH_SURFACE, payload=payload)
        elapsed_ms = (time.perf_counter() - started) * 1000
        try:
            batch = _XSearchBatch.model_validate(json.loads(output_text(response)))
        except (json.JSONDecodeError, ValidationError) as error:
            raise InventoryFetchError("x_search returned an invalid inventory batch") from error

        unique: dict[str, XSearchPost] = {}
        for post in batch.posts:
            unique.setdefault(post.source_url, post)
        posts = tuple(unique.values())
        if len(posts) > search.limit:
            raise InventoryFetchError("x_search returned more posts than requested")
        measurement = measurement_from_response(
            response,
            surface=INVENTORY_FETCH_SURFACE,
            reasoning_effort="low",
            elapsed_ms=elapsed_ms,
        )
        return FetchResult(search=search, posts=posts, measurement=measurement)

    def _payload(self, search: InventorySearch) -> Mapping[str, Any]:
        prompt = (
            "Use x_search to find distinct public X posts matching the query. Return only posts "
            "you found through the tool. Use direct x.com status URLs, exact post text, the author "
            "handle, an ISO date or timestamp, and whether the post has attached media. Do not "
            "invent or reconstruct URLs. Prefer original posts over replies and reposts.\n\n"
            f"Query label: {search.label}\n"
            f"Query: {search.query}\n"
            f"Return at most {search.limit} posts."
        )
        tool: dict[str, Any] = {
            "from_date": search.from_date,
            "to_date": search.to_date,
            "type": "x_search",
        }
        if search.allowed_x_handles:
            tool["allowed_x_handles"] = list(search.allowed_x_handles)
        return {
            "input": [{"content": prompt, "role": "user"}],
            "max_output_tokens": 8192,
            "max_tool_calls": 6,
            "model": self.model,
            "reasoning": {"effort": "low"},
            "store": False,
            "text": {
                "format": {
                    "name": "x_inventory_batch",
                    "schema": _XSearchBatch.model_json_schema(),
                    "strict": True,
                    "type": "json_schema",
                }
            },
            "tools": [tool],
        }


class XStatusDetails(Frozen):
    source_url: str
    text: str = Field(min_length=1)
    author_handle: str = Field(min_length=1)
    created_at: str = Field(min_length=1)
    media_url: str | None = None
    media_width: int | None = Field(default=None, gt=0)
    media_height: int | None = Field(default=None, gt=0)


StatusTransport = Callable[[str], Mapping[str, Any]]


class XStatusResolver:
    """Verify a discovered status through X oEmbed and record compact metadata."""

    def __init__(
        self,
        fixture_store: FixtureStore,
        *,
        transport: StatusTransport | None = None,
        timeout_s: float = 30.0,
    ) -> None:
        self.fixture_store = fixture_store
        self._transport = transport or self._resolve_live
        self.timeout_s = timeout_s

    def resolve(self, source_url: str) -> XStatusDetails:
        canonical = _canonical_status_url(source_url)
        response = self.fixture_store.call(
            STATUS_METADATA_SURFACE,
            {"source_url": canonical},
            lambda: self._transport(canonical),
        )
        try:
            details = XStatusDetails.model_validate(response)
        except ValidationError as error:
            raise InventoryFetchError("X status metadata has an invalid shape") from error
        if details.source_url != canonical:
            raise InventoryFetchError("X status metadata changed the source URL")
        if bool(details.media_width) != bool(details.media_height):
            raise InventoryFetchError("X status metadata has incomplete media dimensions")
        return details

    def _resolve_live(self, source_url: str) -> Mapping[str, Any]:
        oembed_url = "https://publish.twitter.com/oembed?" + urllib.parse.urlencode(
            {"dnt": "true", "omit_script": "true", "url": source_url}
        )
        oembed = self._read_json(oembed_url, allowed_host="publish.twitter.com")
        embed_html = oembed.get("html")
        author_url = oembed.get("author_url")
        if not isinstance(embed_html, str) or not isinstance(author_url, str):
            raise InventoryFetchError("X oEmbed response is missing text or author")

        post_parser = _PostHTMLParser()
        post_parser.feed(embed_html)
        text = " ".join("".join(post_parser.post_text).split())
        text = re.sub(r"\s*pic\.twitter\.com/\w+\s*\Z", "", text).strip()
        if not text:
            raise InventoryFetchError("X oEmbed post text is empty")
        author_handle = urllib.parse.urlparse(author_url).path.strip("/")
        created_at = post_parser.status_date or "unknown"

        page = self._read_text(source_url, allowed_host="x.com")
        meta_parser = _MetaHTMLParser()
        meta_parser.feed(page)
        media_url = meta_parser.values.get("og:image")
        if media_url and "/profile_images/" in media_url:
            media_url = None
        width = _positive_int(meta_parser.values.get("og:image:width")) if media_url else None
        height = _positive_int(meta_parser.values.get("og:image:height")) if media_url else None
        return {
            "author_handle": f"@{author_handle}",
            "created_at": created_at,
            "media_height": height,
            "media_url": media_url,
            "media_width": width,
            "source_url": source_url,
            "text": html.unescape(text),
        }

    def _read_json(self, url: str, *, allowed_host: str) -> Mapping[str, Any]:
        try:
            return cast(
                Mapping[str, Any], json.loads(self._read_text(url, allowed_host=allowed_host))
            )
        except json.JSONDecodeError as error:
            raise InventoryFetchError("X oEmbed returned invalid JSON") from error

    def _read_text(self, url: str, *, allowed_host: str) -> str:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != allowed_host:
            raise InventoryFetchError("refused an unexpected metadata URL")
        request = urllib.request.Request(url, headers={"User-Agent": "AdjacencyCorpus/0.1"})
        try:
            with urllib.request.urlopen(  # nosec B310
                request,
                timeout=self.timeout_s,
            ) as response:
                body = response.read(5_000_001)
        except (urllib.error.HTTPError, urllib.error.URLError) as error:
            raise InventoryFetchError("X status metadata request failed") from error
        if len(body) > 5_000_000:
            raise InventoryFetchError("X status metadata exceeded the size limit")
        return body.decode("utf-8", "replace")


class _PostHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_post = False
        self.in_status_link = False
        self.post_text: list[str] = []
        self.status_link_text: list[str] = []
        self.status_date: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "p":
            self.in_post = True
        if tag == "br" and self.in_post:
            self.post_text.append("\n")
        if tag == "a" and "/status/" in (values.get("href") or ""):
            self.in_status_link = True
            self.status_link_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "p":
            self.in_post = False
        if tag == "a" and self.in_status_link:
            self.status_date = "".join(self.status_link_text).strip() or self.status_date
            self.in_status_link = False

    def handle_data(self, data: str) -> None:
        if self.in_post:
            self.post_text.append(data)
        if self.in_status_link:
            self.status_link_text.append(data)


class _MetaHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.values: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        values = dict(attrs)
        name = values.get("property")
        content = values.get("content")
        if name and content and name not in self.values:
            self.values[name] = content


def _positive_int(value: str | None) -> int | None:
    if value is None or not value.isdigit() or int(value) <= 0:
        return None
    return int(value)
