"""Executable contract for the live xAI transport.

Two layers live here.

The first layer covers the parts of ``adapters/xai_live.py`` that are already
implemented, and it passes now. Most importantly it proves that a payload routed
through :func:`map_provider_response` is admissible by the real bounded client,
so Saturday's work is confined to fetching bytes and naming fields.

The second layer covers the live extract and invoke path against the verified
2026-08-05 field map, including the moving-alias guard that keeps
provider_model_resolved honest.
"""

from __future__ import annotations

import binascii
import struct
import zlib

import pytest

from adjacency.imagine_signal.adapters.xai_live import (
    EDITS_PATH,
    GENERATIONS_PATH,
    MODEL_STANDARD,
    MODEL_STANDARD_DATED,
    TICKS_PER_USD,
    XAI_API_BASE,
    ProviderImagePayload,
    ProviderResponsePayload,
    XAIImagineTransport,
    build_request_body,
    endpoint_for,
    extract_provider_response,
    is_dated_model_alias,
    map_provider_response,
    ticks_to_usd,
    usd_to_ticks,
)
from adjacency.imagine_signal.assets import ContentAddressedAssetStore
from adjacency.imagine_signal.imagine_client import (
    ImagineCallBudgetError,
    ImagineResponseError,
    LiveImagineClient,
)
from adjacency.imagine_signal.ports import (
    BudgetStatus,
    CostMeasurement,
    CostStatus,
    ExternalCallPolicy,
    ImageEditRequest,
    ImageGenerationRequest,
    ImageOperation,
    ImageReference,
    ImagineMode,
    ImagineTransport,
    ProviderCallState,
    ResponseOrigin,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers, matching the conventions in tests/imagine_signal/test_imagine_client.py
# ---------------------------------------------------------------------------


def _png(channel: int = 0, *, width: int = 2, height: int = 2) -> bytes:
    def chunk(name: bytes, payload: bytes) -> bytes:
        checksum = binascii.crc32(name + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + name + payload + struct.pack(">I", checksum)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = bytes([0]) + bytes([channel, 30, 60]) * width
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(row * height))
        + chunk(b"IEND", b"")
    )


_JPEG_BYTES = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb0043000302020302020303030304030304050805050404050a070706080c0a0c0c0b0a0b0b0d0e12100d0e110e0b0b1016101113141515150c0f171816141812141514ffdb00430103040405040509050509140d0b0d1414141414141414141414141414141414141414141414141414141414141414141414141414141414141414141414141414ffc00011080002000203012200021101031101ffc4001f0000010501010101010100000000000000000102030405060708090a0bffc400b5100002010303020403050504040000017d01020300041105122131410613516107227114328191a1082342b1c11552d1f02433627282090a161718191a25262728292a3435363738393a434445464748494a535455565758595a636465666768696a737475767778797a838485868788898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9eaf1f2f3f4f5f6f7f8f9faffc4001f0100030101010101010101010000000000000102030405060708090a0bffc400b51100020102040403040705040400010277000102031104052131061241510761711322328108144291a1b1c109233352f0156272d10a162434e125f11718191a262728292a35363738393a434445464748494a535455565758595a636465666768696a737475767778797a82838485868788898a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae2e3e4e5e6e7e8e9eaf2f3f4f5f6f7f8f9faffda000c03010002110311003f00fcdaa28a2bd33cf3ffd9"
)


def _jpeg() -> bytes:
    return _JPEG_BYTES


def _generation(*, n: int = 1) -> ImageGenerationRequest:
    return ImageGenerationRequest(
        schema_version="1.0",
        model="grok-imagine-image-2026-03-02",
        prompt="Synthetic product on a plain background",
        n=n,
    )


def _edit() -> ImageEditRequest:
    return ImageEditRequest(
        schema_version="1.0",
        model="grok-imagine-image-2026-03-02",
        prompt="Change only the background tone",
        n=1,
        references=(
            ImageReference(
                media_sha256="a" * 64,
                media_type="image/png",
                width=2,
                height=2,
            ),
        ),
    )


def _policy(*, max_calls: int = 1, cost_cap: int = 1_000_000_000) -> ExternalCallPolicy:
    return ExternalCallPolicy(
        approved=True,
        max_calls=max_calls,
        max_outputs_per_call=4,
        max_total_cost_ticks=cost_cap,
    )


def _completed_payload(*, n: int = 1, cost_ticks: int | None = 220_000_000):
    return ProviderResponsePayload(
        state=ProviderCallState.COMPLETED,
        images=tuple(ProviderImagePayload(media_bytes=_png(channel=i)) for i in range(n)),
        provider_request_id="req_synthetic_1",
        provider_model_resolved="grok-imagine-image-2026-03-02",
        moderation_respected=True,
        cost_ticks=cost_ticks,
        latency_ms=420,
    )


class _FakeXAITransport:
    """A transport built exactly the way the real one must be built.

    It skips only the HTTP call. Everything else, meaning the normalized payload
    and the mapper, is the production path. If this satisfies the bounded client,
    so will the real transport once ``invoke`` fetches bytes.
    """

    def __init__(self, payload: ProviderResponsePayload) -> None:
        self.payload = payload
        self.calls: list[tuple[ImageOperation, object]] = []

    def invoke(self, *, operation: ImageOperation, request):
        self.calls.append((operation, request))
        return map_provider_response(self.payload)


# ---------------------------------------------------------------------------
# Layer 1: implemented behavior. These pass today.
# ---------------------------------------------------------------------------


def test_fake_transport_satisfies_the_imagine_transport_protocol():
    transport: ImagineTransport = _FakeXAITransport(_completed_payload())

    assert callable(transport.invoke)


def test_cost_unit_round_trips_and_floors_rather_than_raising_a_cap():
    assert usd_to_ticks(1) == TICKS_PER_USD
    assert ticks_to_usd(TICKS_PER_USD) == pytest.approx(1.0)
    assert usd_to_ticks(0.022) == 220_000_000
    # Flooring matters: a cap must never be silently rounded upward.
    assert usd_to_ticks(0.0000000001999) <= 1


@pytest.mark.parametrize("bad", [-1, -0.5])
def test_negative_dollar_caps_are_rejected(bad):
    with pytest.raises(ValueError):
        usd_to_ticks(bad)


def test_negative_tick_counts_are_rejected():
    with pytest.raises(ValueError):
        ticks_to_usd(-1)


def test_endpoints_match_the_documented_surface():
    assert endpoint_for(ImageOperation.GENERATE) == f"{XAI_API_BASE}{GENERATIONS_PATH}"
    assert endpoint_for(ImageOperation.EDIT) == f"{XAI_API_BASE}{EDITS_PATH}"
    assert endpoint_for(ImageOperation.GENERATE, base="https://example.test/v1/").endswith(
        GENERATIONS_PATH
    )


def test_request_body_emits_confirmed_names_at_the_top_level():
    body = build_request_body(_generation(n=2))

    assert body["model"] == MODEL_STANDARD_DATED
    assert body["n"] == 2
    assert "prompt" in body
    assert body["aspect_ratio"] == "1:1"
    assert body["resolution"] == "1k"
    assert "_unverified" not in body
    assert set(body) >= {"model", "prompt", "n", "aspect_ratio", "resolution"}


def test_edit_request_body_carries_reference_identity():
    body = build_request_body(_edit())

    assert body["reference_media_sha256"] == ["a" * 64]


def test_mapper_reports_exact_cost_when_the_provider_supplies_ticks():
    result = map_provider_response(_completed_payload(cost_ticks=220_000_000))

    assert result.cost == CostMeasurement.known(220_000_000)
    assert result.state == ProviderCallState.COMPLETED
    assert len(result.images) == 1


def test_mapper_reports_unknown_cost_rather_than_inventing_zero_spend():
    result = map_provider_response(_completed_payload(cost_ticks=None))

    assert result.cost.status == CostStatus.UNKNOWN
    assert result.cost.ticks is None


def test_mapper_preserves_a_moderation_rejection_without_images():
    payload = ProviderResponsePayload(
        state=ProviderCallState.MODERATION_REJECTED,
        moderation_respected=True,
        cost_ticks=0,
        error_code="MODERATION_REJECTED",
    )

    result = map_provider_response(payload)

    assert result.state == ProviderCallState.MODERATION_REJECTED
    assert result.images == ()
    assert result.moderation_respected is True
    assert result.error_code == "MODERATION_REJECTED"


def test_mapped_result_is_admissible_by_the_real_bounded_live_client(tmp_path):
    """The load-bearing contract test.

    A payload routed through the mapper must survive the real client's
    validation, asset validation, and cost admission. If this passes, the only
    remaining work in the transport is fetching bytes and naming fields.
    """

    transport = _FakeXAITransport(_completed_payload())
    client = LiveImagineClient(
        transport=transport,
        policy=_policy(),
        asset_store=ContentAddressedAssetStore(tmp_path / "live-assets"),
    )

    result = client.generate(_generation())

    assert result.mode == ImagineMode.LIVE
    assert result.response_origin == ResponseOrigin.LIVE_PROVIDER
    assert result.state == ProviderCallState.COMPLETED
    assert result.budget_status == BudgetStatus.WITHIN_LIMIT
    assert len(result.images) == 1
    assert len(result.images[0].media_sha256) == 64
    assert len(transport.calls) == 1


def test_unknown_cost_blocks_the_next_external_call(tmp_path):
    transport = _FakeXAITransport(_completed_payload(cost_ticks=None))
    client = LiveImagineClient(
        transport=transport,
        policy=_policy(max_calls=2),
        asset_store=ContentAddressedAssetStore(tmp_path / "live-assets"),
    )

    first = client.generate(_generation())
    assert first.budget_status == BudgetStatus.UNKNOWN

    # Reconciliation is required before spending again. This is the property that
    # protects an unattended 2 AM loop.
    with pytest.raises(ImagineCallBudgetError) as caught:
        client.generate(_generation())
    assert "reconcil" in str(caught.value).lower()


def test_completed_result_missing_provider_metadata_is_refused(tmp_path):
    payload = ProviderResponsePayload(
        state=ProviderCallState.COMPLETED,
        images=(ProviderImagePayload(media_bytes=_png()),),
        provider_request_id=None,
        provider_model_resolved="grok-imagine-image-2026-03-02",
        moderation_respected=True,
        cost_ticks=1,
        latency_ms=10,
    )
    client = LiveImagineClient(
        transport=_FakeXAITransport(payload),
        policy=_policy(),
        asset_store=ContentAddressedAssetStore(tmp_path / "live-assets"),
    )

    with pytest.raises(ImagineResponseError):
        client.generate(_generation())


# ---------------------------------------------------------------------------
# Layer 2: live transport against the verified 2026-08-05 field map.
# ---------------------------------------------------------------------------


def _verified_raw_response() -> dict[str, object]:
    # Shape confirmed by two authorized smoke probes. The URL value is synthetic
    # and is never written to a fixture; tests inject a media_fetcher.
    return {
        "data": [
            {
                "url": "https://api.x.ai/v1/images/synthetic-test-object",
                "mime_type": "image/jpeg",
            }
        ],
        "usage": {"cost_in_usd_ticks": 200_000_000},
    }


def _verified_headers() -> dict[str, str]:
    return {
        "x-request-id": "448d3a86-0836-933a-88fb-45158e41a892",
        "x-metrics-e2e-ms": "5312.4",
        "x-zero-data-retention": "false",
        "x-data-retention": "general",
    }


def test_extract_preserves_completion_invariants():
    """Completed extraction carries the three fields the bounded client requires."""

    raw = _verified_raw_response()
    headers = _verified_headers()

    payload = extract_provider_response(
        raw,
        headers=headers,
        latency_ms=5428,
        requested_model=MODEL_STANDARD_DATED,
        media_fetcher=lambda url: (_jpeg(), "image/jpeg"),
    )

    assert payload.state == ProviderCallState.COMPLETED
    assert payload.provider_request_id == headers["x-request-id"]
    assert payload.provider_model_resolved == MODEL_STANDARD_DATED
    assert payload.moderation_respected is True
    assert payload.images and payload.images[0].media_bytes == _jpeg()
    assert payload.images[0].declared_content_type == "image/jpeg"
    assert payload.cost_ticks == 200_000_000
    # Prefer server-side e2e latency when the header is present.
    assert payload.latency_ms == 5312


def test_invoke_issues_exactly_one_request_and_returns_a_mapped_result():
    """One request, no retry, no fallback, and a normalized COMPLETED result."""

    seen: list[str] = []

    def fake_http(
        *, method: str, url: str, json_body: dict[str, object]
    ) -> tuple[dict[str, object], dict[str, str]]:
        seen.append(url)
        assert method == "POST"
        assert json_body["model"] == MODEL_STANDARD_DATED
        assert "_unverified" not in json_body
        return _verified_raw_response(), _verified_headers()

    transport = XAIImagineTransport(http=fake_http)

    # Avoid a real network media fetch in the unit test by monkeypatching.
    import adjacency.imagine_signal.adapters.xai_live as live

    original = live.fetch_provider_media
    live.fetch_provider_media = lambda url, timeout_seconds=30.0: (_jpeg(), "image/jpeg")  # type: ignore[assignment]
    try:
        result = transport.invoke(operation=ImageOperation.GENERATE, request=_generation())
    finally:
        live.fetch_provider_media = original  # type: ignore[assignment]

    assert len(seen) == 1
    assert seen[0] == f"{XAI_API_BASE}{GENERATIONS_PATH}"
    assert transport.calls_made == 1
    assert result.state == ProviderCallState.COMPLETED
    assert result.provider_request_id == _verified_headers()["x-request-id"]
    assert result.provider_model_resolved == MODEL_STANDARD_DATED
    assert result.moderation_respected is True
    assert result.cost.ticks == 200_000_000
    assert len(result.images) == 1
    assert result.images[0].media_bytes == _jpeg()


def test_moving_alias_guard_fails_closed_on_resolved_model():
    """A moving alias must not invent provider_model_resolved."""

    assert is_dated_model_alias(MODEL_STANDARD) is False
    assert is_dated_model_alias(MODEL_STANDARD_DATED) is True

    payload = extract_provider_response(
        _verified_raw_response(),
        headers=_verified_headers(),
        latency_ms=100,
        requested_model=MODEL_STANDARD,
        media_fetcher=lambda url: (_jpeg(), "image/jpeg"),
    )
    assert payload.provider_model_resolved is None

    # The bounded client must refuse a COMPLETED result missing resolved model.
    from adjacency.imagine_signal.assets import ContentAddressedAssetStore
    from adjacency.imagine_signal.imagine_client import ImagineResponseError, LiveImagineClient

    class _MovingAliasTransport:
        def invoke(self, *, operation, request):
            return map_provider_response(payload)

    client = LiveImagineClient(
        transport=_MovingAliasTransport(),
        policy=_policy(),
        asset_store=ContentAddressedAssetStore(
            __import__("pathlib").Path("/tmp/adj-live-assets-test")
        ),
    )
    moving_request = ImageGenerationRequest(
        schema_version="1.0",
        model=MODEL_STANDARD,
        prompt="Synthetic product on a plain background",
        n=1,
    )
    with pytest.raises(ImagineResponseError):
        client.generate(moving_request)


def test_standard_model_constant_is_the_documented_exploration_model():
    assert MODEL_STANDARD == "grok-imagine-image"
    assert MODEL_STANDARD_DATED == "grok-imagine-image-2026-03-02"


# ---------------------------------------------------------------------------
# Dated-alias parsing. xAI publishes BOTH -YYYY-MM-DD and -YYYYMMDD forms
# (05_XAI_INTEGRATION.md section 3), and handling only one silently rejects a
# legitimate alias. Fail-closed, but wrong.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model",
    [
        "grok-imagine-image-2026-03-02",
        "grok-imagine-image-quality-20260403",
    ],
)
def test_both_documented_dated_alias_formats_are_accepted(model):
    assert is_dated_model_alias(model) is True


@pytest.mark.parametrize(
    "model",
    [
        "grok-imagine-image",
        "grok-imagine-image-quality",
        "grok-imagine-image-quality-latest",
        "grok-imagine-image-latest",
        "",
        "   ",
        "grok-imagine-image-20261301",
        "grok-imagine-image-2026-13-02",
        "grok-imagine-image-19990101",
    ],
)
def test_moving_or_implausible_aliases_are_refused(model):
    assert is_dated_model_alias(model) is False


def test_quality_dated_constant_is_actually_dated():
    """MODEL_QUALITY_DATED once held the MOVING alias, which made the name a lie."""

    from adjacency.imagine_signal.adapters.xai_live import (
        MODEL_QUALITY,
        MODEL_QUALITY_DATED,
    )

    assert MODEL_QUALITY_DATED != MODEL_QUALITY
    assert is_dated_model_alias(MODEL_QUALITY_DATED) is True
