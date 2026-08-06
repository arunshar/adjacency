"""xAI Imagine transport for the Grokathon live slice.

Field names and header names are taken from the authorized smoke probes
recorded in ``hackathon/COST_LEDGER.md`` section 1. The transport is the only
seam between ImagineSignal and xAI.

Nothing in this module reads an environment variable or looks up a credential.
The caller injects an authorized HTTP callable. Image bytes arrive inline via
``response_format=b64_json`` (probe-confirmed for generations 2026-08-06).
Signed URLs and base64 strings are never written into logs, fixtures, or
artifacts.
"""

from __future__ import annotations

import base64
import binascii
import ipaddress
import socket
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlparse

from adjacency.imagine_signal.assets import (
    AssetDescriptor,
    AssetValidationError,
    ContentAddressedAssetStore,
)
from adjacency.imagine_signal.ports import (
    CostMeasurement,
    ImageEditRequest,
    ImageGenerationRequest,
    ImageOperation,
    ImageReference,
    ImagineRequest,
    ProviderCallState,
    ProviderOutcomeUnknownError,
    TransportImage,
    TransportResult,
)

# ---------------------------------------------------------------------------
# Verified provider facts
#
# Every constant below is sourced from docs/imagine_signal/05_XAI_INTEGRATION.md,
# which was verified against official xAI documentation on 2026-08-05. Refresh
# that document before trusting any price or limit for budgeting or review.
# ---------------------------------------------------------------------------

XAI_API_BASE = "https://api.x.ai/v1"
GENERATIONS_PATH = "/images/generations"
EDITS_PATH = "/images/edits"
MODEL_DISCOVERY_PATH = "/image-generation-models"

#: Moving alias. Convenient for exploration, but it can silently substitute a
#: different underlying model. Do not use it for evaluation requests: resolved
#: model is absent from the provider response, so only a dated alias makes
#: setting provider_model_resolved from the request honest.
MODEL_STANDARD = "grok-imagine-image"
MODEL_QUALITY = "grok-imagine-image-quality"

#: Dated alias used for evaluation and live transport defaults. A dated alias
#: cannot silently substitute, so resolved may equal requested.
MODEL_STANDARD_DATED = "grok-imagine-image-2026-03-02"

#: Documented in 05_XAI_INTEGRATION.md section 3 but NOT yet exercised by a smoke
#: probe, unlike MODEL_STANDARD_DATED. Note the compact date format: xAI publishes
#: both -YYYY-MM-DD and -YYYYMMDD, which is why is_dated_model_alias accepts both.
MODEL_QUALITY_DATED = "grok-imagine-image-quality-20260403"

#: Moving aliases that must not be treated as resolved-model truth.
MOVING_MODEL_ALIASES = frozenset({MODEL_STANDARD, MODEL_QUALITY})

#: Inline image output. Probe-confirmed for generations 2026-08-06
#: (hackathon/COST_LEDGER.md, "base64 output works, and it deletes the whole
#: fetch problem"). UNCONFIRMED for edits until an edit probe verifies it;
#: still emitted on edit requests so the provider can accept the same shape.
RESPONSE_FORMAT_B64_JSON = "b64_json"

#: Exact content types admitted for decoded image bytes. Deliberately not a
#: startswith("image/") test, which would admit image/svg+xml.
ALLOWED_MEDIA_TYPES = frozenset({"image/jpeg", "image/jpg", "image/png"})
MAX_MEDIA_BYTES = 12 * 1024 * 1024
HTTP_TIMEOUT_SECONDS = 60.0

# ---------------------------------------------------------------------------
# URL-fetch path: UNREFERENCED as of 2026-08-06.
#
# Live path now uses response_format=b64_json (see COST_LEDGER.md section
# "base64 output works, and it deletes the whole fetch problem"). These
# symbols stay for Saturday cleanup deletion candidates. Do not call them
# from extract_provider_response. Do not silently fall back to them when
# b64_json is absent.
# ---------------------------------------------------------------------------
ALLOWED_MEDIA_HOSTS = frozenset({"api.x.ai", "imgen.x.ai"})
MEDIA_FETCH_TIMEOUT_SECONDS = 30.0
MAX_MEDIA_REDIRECTS = 0

#: Documented cost unit. 10,000,000,000 ticks equal one US dollar.
TICKS_PER_USD = 10_000_000_000

#: Documented provider rate limit, in requests per second, per image model.
MAX_REQUESTS_PER_SECOND = 5

#: Documented maximum reference images for a multi-image edit.
MAX_REFERENCE_IMAGES = 3


def usd_to_ticks(usd: float) -> int:
    """Convert a US dollar cap into the provider's integer tick unit.

    Rounds down so a configured cap is never silently raised.
    """

    if usd < 0:
        raise ValueError("cost cap cannot be negative")
    return int(usd * TICKS_PER_USD)


def ticks_to_usd(ticks: int) -> float:
    """Convert provider ticks back to US dollars for a human-readable ledger."""

    if ticks < 0:
        raise ValueError("tick count cannot be negative")
    return ticks / TICKS_PER_USD


# ---------------------------------------------------------------------------
# VERIFIED provider response shape
#
# Prefer (2026-08-06 b64_json probe):
#   data[0].b64_json             standard base64 image bytes (not logged)
#   data[0].mime_type            image/jpeg
#   usage.cost_in_usd_ticks      exact request cost
# Legacy URL shape (abandoned; must not be fetched if b64 was requested):
#   data[0].url                  temporary image URL
# Headers:
#   x-request-id                 provider request id (body has none)
#   x-metrics-e2e-ms             server-side latency when present
# Absent:
#   resolved model               set from requested only for dated aliases
#   moderation disposition       True on COMPLETED only
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProviderImagePayload:
    """One decoded provider image, already in memory.

    Built from inline ``b64_json`` (preferred) at the extract boundary. This
    dataclass only carries the resulting bytes so the mapper stays pure and
    testable. The base64 string itself is never stored here.
    """

    media_bytes: bytes
    declared_content_type: str | None = None
    declared_width: int | None = None
    declared_height: int | None = None
    expected_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderResponsePayload:
    """Normalized provider response, independent of xAI JSON field names.

    Building this object is the only place that needs the real field names.
    Everything downstream consumes this typed shape instead.
    """

    state: ProviderCallState
    images: tuple[ProviderImagePayload, ...] = ()
    provider_request_id: str | None = None
    provider_model_resolved: str | None = None
    moderation_respected: bool | None = None
    cost_ticks: int | None = None
    latency_ms: int | None = None
    error_code: str | None = None


class HttpCallable(Protocol):
    """Injected HTTP surface. Performs exactly one request and returns JSON plus headers."""

    def __call__(
        self,
        *,
        method: str,
        url: str,
        json_body: dict[str, object],
    ) -> tuple[dict[str, object], Mapping[str, str]]:
        """Issue one authorized request. Retry and fallback are intentionally absent.

        Returns ``(json_body, response_headers)``. Header keys should be lower-cased.
        """


# ---------------------------------------------------------------------------
# Request construction
# ---------------------------------------------------------------------------

#: Maps an ImagineSignal operation onto its documented endpoint path.
OPERATION_PATHS: dict[ImageOperation, str] = {
    ImageOperation.GENERATE: GENERATIONS_PATH,
    ImageOperation.EDIT: EDITS_PATH,
}


def endpoint_for(operation: ImageOperation, *, base: str = XAI_API_BASE) -> str:
    """Return the full endpoint URL for a semantic operation."""

    try:
        path = OPERATION_PATHS[operation]
    except KeyError as error:  # pragma: no cover - StrEnum is closed
        raise ValueError(f"unsupported operation: {operation!r}") from error
    return f"{base.rstrip('/')}{path}"


def _extension_for_media_type(media_type: str) -> str:
    if media_type == "image/png":
        return "png"
    if media_type == "image/jpeg":
        return "jpg"
    raise ValueError(f"unsupported reference media_type: {media_type}")


def resolve_edit_reference_bytes(
    reference: ImageReference,
    asset_store: ContentAddressedAssetStore,
) -> bytes:
    """Resolve identity-only ImageReference to verified bytes at the send boundary.

    Contracts keep digests only. The transport is the last place that may touch
    bytes, and only after ``read_verified`` rechecks every declared property.
    """

    extension = _extension_for_media_type(reference.media_type)
    path = asset_store.root / f"{reference.media_sha256}.{extension}"
    if not path.is_file():
        raise AssetValidationError(
            "ASSET_MISSING",
            f"edit reference blob is missing for digest {reference.media_sha256}",
        )
    # Length is not on ImageReference; take it from the stored blob, then let
    # read_verified re-hash and re-check every declared field.
    provisional = AssetDescriptor(
        media_sha256=reference.media_sha256,
        byte_length=path.stat().st_size,
        content_type=reference.media_type,
        width=reference.width,
        height=reference.height,
        extension=extension,
    )
    return asset_store.read_verified(provisional)


def reference_to_data_uri(media_bytes: bytes, *, media_type: str) -> str:
    """Encode verified bytes as the data URI shape the edits endpoint accepts."""

    if not media_bytes:
        raise ValueError("edit reference bytes are empty")
    encoded = base64.standard_b64encode(media_bytes).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def build_request_body(
    request: ImagineRequest,
    *,
    asset_store: ContentAddressedAssetStore | None = None,
) -> dict[str, object]:
    """Build the provider request body from a validated ImagineSignal request.

    Generation and edit both emit ``model``, ``prompt``, ``n``, ``aspect_ratio``,
    ``resolution``, and ``response_format: "b64_json"`` at the top level.

    ``response_format=b64_json`` is probe-confirmed for generations
    (2026-08-06). It is UNCONFIRMED for edits until an edit probe verifies it;
    it is still emitted so both operations share one extract path.

    Edit also emits ``image.url`` as a ``data:<media_type>;base64,...`` URI
    (confirmed 2026-08-05). ``ImageReference`` still carries identity only;
    bytes are resolved from ``asset_store`` at this boundary via
    ``read_verified``.
    """

    body: dict[str, object] = {
        "model": request.model,
        "prompt": request.prompt,
        "n": request.n,
        "aspect_ratio": request.aspect_ratio,
        "resolution": request.resolution,
        # Confirmed for generations 2026-08-06. UNCONFIRMED for edits.
        "response_format": RESPONSE_FORMAT_B64_JSON,
    }
    if isinstance(request, ImageEditRequest):
        if asset_store is None:
            raise ValueError("ImageEditRequest requires an asset_store to resolve reference bytes")
        if len(request.references) != 1:
            raise ValueError(
                "only a single edit reference is supported until the multi-image "
                "request shape is verified by a smoke probe"
            )
        reference = request.references[0]
        media_bytes = resolve_edit_reference_bytes(reference, asset_store)
        body["image"] = {"url": reference_to_data_uri(media_bytes, media_type=reference.media_type)}
    return body


# ---------------------------------------------------------------------------
# Response mapping. Pure, fully implemented, and covered by contract tests.
# ---------------------------------------------------------------------------


def map_provider_response(payload: ProviderResponsePayload) -> TransportResult:
    """Map a normalized provider payload onto the ImagineSignal transport result.

    This function performs no validation of its own. The bounded external client
    in ``imagine_client._ExternalImagineClient._validate_transport_result`` is the
    single authority on whether a result is admissible, and duplicating that
    logic here would create two places to keep in agreement.

    Cost is reported as exact ticks only when the provider supplied them. A
    missing cost maps to an explicit unknown, which blocks further external calls
    until it is reconciled rather than silently recording zero spend.
    """

    cost = (
        CostMeasurement.known(payload.cost_ticks)
        if payload.cost_ticks is not None
        else CostMeasurement.unknown()
    )
    images = tuple(
        TransportImage(
            media_bytes=image.media_bytes,
            declared_content_type=image.declared_content_type,
            declared_width=image.declared_width,
            declared_height=image.declared_height,
            expected_sha256=image.expected_sha256,
        )
        for image in payload.images
    )
    return TransportResult(
        state=payload.state,
        images=images,
        provider_request_id=payload.provider_request_id,
        provider_model_resolved=payload.provider_model_resolved,
        moderation_respected=payload.moderation_respected,
        cost=cost,
        latency_ms=payload.latency_ms,
        error_code=payload.error_code,
    )


def is_dated_model_alias(model: str) -> bool:
    """Return whether a model id is a dated alias rather than a moving one.

    xAI publishes dated aliases in TWO formats, both listed in
    ``docs/imagine_signal/05_XAI_INTEGRATION.md`` section 3:

    - dashed, ``grok-imagine-image-2026-03-02``
    - compact, ``grok-imagine-image-quality-20260403``

    Handling only the dashed form rejects a legitimate dated alias. That fails
    closed rather than open, so it is safe, but it would block the quality model
    for no good reason. A ``-latest`` suffix is explicitly NOT dated: it moves.
    """

    normalized = model.strip()
    if not normalized or normalized in MOVING_MODEL_ALIASES:
        return False
    if normalized.endswith("-latest"):
        return False

    # Compact form: trailing -YYYYMMDD
    tail = normalized.rsplit("-", 1)
    if len(tail) == 2 and len(tail[1]) == 8 and tail[1].isdigit():
        return _plausible_ymd(tail[1][:4], tail[1][4:6], tail[1][6:])

    # Dashed form: trailing -YYYY-MM-DD
    parts = normalized.rsplit("-", 3)
    if len(parts) != 4:
        return False
    return _plausible_ymd(parts[1], parts[2], parts[3])


def _plausible_ymd(year: str, month: str, day: str) -> bool:
    """Return whether three strings look like a calendar date in a model alias."""

    if not (year.isdigit() and month.isdigit() and day.isdigit()):
        return False
    if len(year) != 4 or len(month) != 2 or len(day) != 2:
        return False
    return 2020 <= int(year) <= 2100 and 1 <= int(month) <= 12 and 1 <= int(day) <= 31


def _header_map(headers: Mapping[str, str] | None) -> dict[str, str]:
    if not headers:
        return {}
    return {str(key).lower(): str(value) for key, value in headers.items()}


def _looks_like_moderation_rejection(raw: dict[str, object], headers: Mapping[str, str]) -> bool:
    for key in ("error", "error_code", "code", "status"):
        value = raw.get(key)
        if isinstance(value, str) and "moderation" in value.lower():
            return True
        if isinstance(value, dict):
            joined = " ".join(str(item).lower() for item in value.values())
            if "moderation" in joined:
                return True
    for key, value in headers.items():
        if "moderation" in key.lower() and str(value).lower() in {"rejected", "true", "blocked"}:
            return True
    return False


def _host_allowed(hostname: str | None) -> bool:
    """UNREFERENCED 2026-08-06. URL-fetch abandoned for b64_json. Cleanup candidate."""

    if not hostname:
        return False
    host = hostname.lower().rstrip(".")
    if host in ALLOWED_MEDIA_HOSTS:
        return True
    return any(host.endswith(f".{allowed}") for allowed in ALLOWED_MEDIA_HOSTS)


def _assert_host_resolves_public(hostname: str) -> None:
    """UNREFERENCED 2026-08-06. URL-fetch abandoned for b64_json. Cleanup candidate."""

    try:
        infos = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise ValueError(f"media host could not be resolved: {hostname}") from error
    if not infos:
        raise ValueError(f"media host resolved to no addresses: {hostname}")
    for info in infos:
        address = info[4][0]
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError as error:
            raise ValueError(f"media host resolved to an unparseable address: {address}") from error
        if (
            parsed.is_private
            or parsed.is_loopback
            or parsed.is_link_local
            or parsed.is_multicast
            or parsed.is_reserved
            or parsed.is_unspecified
        ):
            raise ValueError(f"media host resolved to a non-public address: {address}")


def fetch_provider_media(
    url: str, *, timeout_seconds: float = MEDIA_FETCH_TIMEOUT_SECONDS
) -> tuple[bytes, str | None]:
    """UNREFERENCED 2026-08-06. URL-fetch path abandoned for b64_json.

    Kept for Saturday cleanup deletion. Do not call from extract_provider_response.
    See COST_LEDGER.md section "base64 output works, and it deletes the whole
    fetch problem". Never logs the URL. Redirects are refused. Size and
    content-type are bounded.
    """

    if not isinstance(url, str) or not url.strip():
        raise ValueError("media URL is missing")
    parsed = urlparse(url.strip())
    if parsed.scheme != "https":
        raise ValueError("media URL must use https")
    if parsed.username or parsed.password:
        raise ValueError("media URL must not carry credentials")
    if not _host_allowed(parsed.hostname):
        raise ValueError("media URL host is outside the xAI media allowlist")
    # Not an assert. `python -O` strips asserts, and bandit B101 fails CI on one
    # inside a security boundary even when, as here, _host_allowed has already
    # rejected every falsy hostname. Raising keeps the mypy narrowing and cannot
    # be compiled away.
    hostname = parsed.hostname
    if hostname is None:
        raise ValueError("media URL has no host")
    _assert_host_resolves_public(hostname)

    request = urllib.request.Request(  # noqa: S310 - host allowlisted and scheme fixed
        url.strip(),
        method="GET",
        headers={"Accept": "image/jpeg,image/png,image/*;q=0.8"},
    )

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
            raise ValueError(f"media fetch refused HTTP redirect ({code})")

    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=timeout_seconds) as response:  # noqa: S310
            final_host = urlparse(response.geturl()).hostname
            if not _host_allowed(final_host):
                raise ValueError("media fetch landed outside the xAI media allowlist")
            content_type = response.headers.get("Content-Type")
            if content_type:
                media_type = content_type.split(";", 1)[0].strip().lower()
                # Exact allowlist, not a startswith("image/") test. The looser form
                # admits image/svg+xml, which is a script-bearing format. assets.py
                # would reject it downstream, but the boundary should refuse it here.
                if media_type not in ALLOWED_MEDIA_TYPES:
                    raise ValueError(f"media content-type is not an admitted image: {media_type}")
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_MEDIA_BYTES:
                    raise ValueError(f"media exceeds the {MAX_MEDIA_BYTES} byte cap")
                chunks.append(chunk)
    except urllib.error.HTTPError as error:
        raise ValueError(f"media fetch failed with HTTP {error.code}") from error
    except urllib.error.URLError as error:
        raise ValueError(f"media fetch failed: {error.reason}") from error

    media_bytes = b"".join(chunks)
    if not media_bytes:
        raise ValueError("media fetch returned empty body")
    declared = None
    if content_type:
        declared = content_type.split(";", 1)[0].strip().lower()
        if declared == "image/jpg":
            declared = "image/jpeg"
    return media_bytes, declared


def _max_b64_encoded_chars_for_media_cap(max_decoded_bytes: int = MAX_MEDIA_BYTES) -> int:
    """Upper bound on standard-base64 character count for a decoded-size cap.

    standard_b64 expands 3 bytes to 4 chars, with padding to a multiple of 4.
    Using the padded ceiling refuses oversized payloads before decode.
    """

    if max_decoded_bytes < 0:
        raise ValueError("max_decoded_bytes cannot be negative")
    # ceil(n / 3) * 4
    return ((max_decoded_bytes + 2) // 3) * 4


def decode_inline_b64_image(
    b64_json: object,
    *,
    max_decoded_bytes: int = MAX_MEDIA_BYTES,
) -> bytes:
    """Decode ``data[0].b64_json`` under the media size cap. Never logs the string.

    Encoded length is checked before ``b64decode`` so an oversized payload cannot
    be materialised into a full decoded buffer first.
    """

    if not isinstance(b64_json, str) or not b64_json.strip():
        raise ValueError("provider image entry is missing b64_json")
    # Whitespace is legal in some base64 transports; strip only ends, never log.
    encoded = b64_json.strip()
    max_encoded = _max_b64_encoded_chars_for_media_cap(max_decoded_bytes)
    if len(encoded) > max_encoded:
        raise ValueError(
            f"inline b64_json exceeds the {max_decoded_bytes} byte decoded media cap "
            f"(encoded length {len(encoded)} > {max_encoded})"
        )
    try:
        # stdlib standard_b64decode has no validate= kwarg on all supported Pythons.
        media_bytes = base64.standard_b64decode(encoded)
    except (binascii.Error, ValueError) as error:
        raise ValueError("provider b64_json is not valid standard base64") from error
    if not media_bytes:
        raise ValueError("provider b64_json decoded to empty bytes")
    if len(media_bytes) > max_decoded_bytes:
        raise ValueError(f"decoded inline image exceeds the {max_decoded_bytes} byte media cap")
    return media_bytes


def extract_provider_response(
    raw: dict[str, object],
    *,
    headers: Mapping[str, str] | None = None,
    latency_ms: int,
    requested_model: str | None = None,
    media_fetcher=None,
) -> ProviderResponsePayload:
    """Translate a raw xAI JSON response and headers into the normalized payload.

    Image bytes come from inline ``data[0].b64_json`` (COST_LEDGER.md,
    2026-08-06). ``media_fetcher`` is accepted for call-site compatibility but
    is never used: a URL-only response after requesting b64_json is a hard
    failure, not a silent fetch fallback.

    Order: moderation rejection, cost ticks, image bytes, then request id,
    resolved model, and moderation_respected.
    """

    del media_fetcher  # deliberately unused; URL fetch path is abandoned

    if not isinstance(raw, dict):
        raise ValueError("provider response must be a JSON object")
    header_map = _header_map(headers)

    # 1. Moderation rejection first.
    if _looks_like_moderation_rejection(raw, header_map):
        return ProviderResponsePayload(
            state=ProviderCallState.MODERATION_REJECTED,
            images=(),
            provider_request_id=header_map.get("x-request-id") or None,
            provider_model_resolved=None,
            moderation_respected=True,
            cost_ticks=_read_cost_ticks(raw),
            latency_ms=_prefer_latency_ms(header_map, latency_ms),
            error_code="MODERATION_REJECTED",
        )

    # 2. Cost.
    cost_ticks = _read_cost_ticks(raw)

    # 3. Image bytes from data[0].b64_json only. No URL fetch fallback.
    data = raw.get("data")
    if not isinstance(data, list) or not data:
        raise ValueError("provider response is missing data[] images")
    first = data[0]
    if not isinstance(first, dict):
        raise ValueError("provider image entry must be an object")

    mime_type = first.get("mime_type")
    declared_content_type = str(mime_type).strip().lower() if isinstance(mime_type, str) else None
    if declared_content_type == "image/jpg":
        declared_content_type = "image/jpeg"

    b64_json = first.get("b64_json")
    image_url = first.get("url")
    if isinstance(b64_json, str) and b64_json.strip():
        media_bytes = decode_inline_b64_image(b64_json)
    elif isinstance(image_url, str) and image_url.strip():
        # Provider ignored response_format=b64_json. Do NOT fetch. Silent
        # fallback to the abandoned URL path is refused by design.
        raise ProviderOutcomeUnknownError(
            "provider returned data[0].url after response_format=b64_json was "
            "requested; refusing silent URL-fetch fallback",
            provider_request_id=header_map.get("x-request-id") or None,
        )
    else:
        raise ValueError("provider image entry is missing b64_json")

    images = (
        ProviderImagePayload(
            media_bytes=media_bytes,
            declared_content_type=declared_content_type,
        ),
    )

    # 4. provider_request_id from header only.
    provider_request_id = header_map.get("x-request-id") or None
    if provider_request_id is not None:
        provider_request_id = provider_request_id.strip() or None

    # Resolved model: only from a dated requested alias.
    provider_model_resolved = None
    if requested_model is not None and is_dated_model_alias(requested_model):
        provider_model_resolved = requested_model.strip()

    # moderation_respected True on COMPLETED only.
    return ProviderResponsePayload(
        state=ProviderCallState.COMPLETED,
        images=images,
        provider_request_id=provider_request_id,
        provider_model_resolved=provider_model_resolved,
        moderation_respected=True,
        cost_ticks=cost_ticks,
        latency_ms=_prefer_latency_ms(header_map, latency_ms),
        error_code=None,
    )


def _read_cost_ticks(raw: dict[str, object]) -> int | None:
    usage = raw.get("usage")
    if not isinstance(usage, dict):
        return None
    ticks = usage.get("cost_in_usd_ticks")
    if isinstance(ticks, bool) or not isinstance(ticks, int):
        return None
    if ticks < 0:
        raise ValueError("provider cost_in_usd_ticks cannot be negative")
    return ticks


def _prefer_latency_ms(headers: Mapping[str, str], measured_latency_ms: int) -> int:
    raw = headers.get("x-metrics-e2e-ms")
    if raw is None:
        return measured_latency_ms
    try:
        value = float(raw)
    except ValueError:
        return measured_latency_ms
    if value < 0:
        return measured_latency_ms
    return int(value)


# ---------------------------------------------------------------------------
# Transport skeleton
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class XAIImagineTransport:
    """Injected-HTTP xAI transport satisfying the ImagineTransport protocol.

    Construction never reads ``XAI_API_KEY``. The caller supplies an already
    authorized ``http`` callable, which keeps credential handling outside this
    module and outside every test.

    ``asset_store`` is required for edit requests so reference digests can be
    resolved to bytes at send time without putting blobs on ``ImageReference``.

    The bounded call budget lives in
    :class:`~adjacency.imagine_signal.ports.ExternalCallPolicy` and is enforced by
    the external client before ``invoke`` is ever reached. Do not add a second
    budget check here, and do not add retry or fallback. A single invocation that
    fails is a fact to report, not a condition to paper over.
    """

    http: HttpCallable
    asset_store: ContentAddressedAssetStore | None = None
    base_url: str = XAI_API_BASE
    calls_made: int = field(default=0, init=False)

    def invoke(
        self,
        *,
        operation: ImageOperation,
        request: ImagineRequest,
    ) -> TransportResult:
        """Invoke once. No retry, no fallback.

        Sequence:
        1. Build endpoint and request body (top-level fields only; edits resolve
           reference bytes from the asset store into a data URI).
        2. Issue exactly one HTTP request and record elapsed client latency.
        3. On timeout or ambiguous failure after the request was sent, raise
           ``ProviderOutcomeUnknownError`` with any known provider request id.
        4. Extract, map, and return the transport result.
        """

        url = endpoint_for(operation, base=self.base_url)
        body = build_request_body(request, asset_store=self.asset_store)
        started = time.monotonic()
        provider_request_id: str | None = None
        request_sent = False
        try:
            request_sent = True
            raw, response_headers = self.http(method="POST", url=url, json_body=body)
            self.calls_made += 1
        except ProviderOutcomeUnknownError:
            raise
        except TimeoutError as error:
            raise ProviderOutcomeUnknownError(
                "provider request timed out after the request was sent",
                provider_request_id=provider_request_id,
            ) from error
        except urllib.error.HTTPError as error:
            # HTTP error means the server responded; try to surface request id.
            header_id = None
            try:
                header_id = error.headers.get("x-request-id") if error.headers is not None else None
            except Exception:
                header_id = None
            raise ProviderOutcomeUnknownError(
                f"provider returned HTTP {error.code} after the request was sent",
                provider_request_id=header_id,
            ) from error
        except urllib.error.URLError as error:
            reason = getattr(error, "reason", error)
            if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
                raise ProviderOutcomeUnknownError(
                    "provider request timed out after the request was sent",
                    provider_request_id=provider_request_id,
                ) from error
            if request_sent:
                raise ProviderOutcomeUnknownError(
                    f"provider outcome unknown after the request was sent: {reason}",
                    provider_request_id=provider_request_id,
                ) from error
            raise
        except Exception as error:
            if request_sent:
                raise ProviderOutcomeUnknownError(
                    f"provider outcome unknown after the request was sent: {error}",
                    provider_request_id=provider_request_id,
                ) from error
            raise

        elapsed_ms = int((time.monotonic() - started) * 1000)
        if not isinstance(raw, dict):
            raise ProviderOutcomeUnknownError(
                "provider returned a non-object JSON body after the request was sent",
                provider_request_id=_header_map(response_headers).get("x-request-id"),
            )
        try:
            payload = extract_provider_response(
                raw,
                headers=response_headers,
                latency_ms=elapsed_ms,
                requested_model=request.model,
            )
        except ProviderOutcomeUnknownError:
            # extract already classified the outcome (e.g. URL after b64 request).
            raise
        except Exception as error:
            header_id = _header_map(response_headers).get("x-request-id")
            raise ProviderOutcomeUnknownError(
                f"provider response could not be reconciled: {error}",
                provider_request_id=header_id,
            ) from error
        return map_provider_response(payload)


def is_generation(request: ImagineRequest) -> bool:
    """Return whether a request is a text-to-image generation rather than an edit."""

    return isinstance(request, ImageGenerationRequest)


__all__ = [
    "ALLOWED_MEDIA_HOSTS",
    "EDITS_PATH",
    "GENERATIONS_PATH",
    "MAX_MEDIA_BYTES",
    "MAX_REFERENCE_IMAGES",
    "MAX_REQUESTS_PER_SECOND",
    "MODEL_DISCOVERY_PATH",
    "MODEL_QUALITY",
    "MODEL_STANDARD",
    "MODEL_STANDARD_DATED",
    "MOVING_MODEL_ALIASES",
    "OPERATION_PATHS",
    "RESPONSE_FORMAT_B64_JSON",
    "TICKS_PER_USD",
    "XAI_API_BASE",
    "HttpCallable",
    "ProviderImagePayload",
    "ProviderResponsePayload",
    "XAIImagineTransport",
    "build_request_body",
    "decode_inline_b64_image",
    "endpoint_for",
    "extract_provider_response",
    "fetch_provider_media",
    "is_dated_model_alias",
    "is_generation",
    "map_provider_response",
    "reference_to_data_uri",
    "resolve_edit_reference_bytes",
    "ticks_to_usd",
    "usd_to_ticks",
]
