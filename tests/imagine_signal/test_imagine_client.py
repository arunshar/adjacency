from __future__ import annotations

import binascii
import struct
import zlib
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from adjacency.imagine_signal.adapters.fixture_blobs import (
    BinaryFixtureMissError,
    BinaryFixtureSecretError,
    BinaryFixtureStore,
)
from adjacency.imagine_signal.assets import ContentAddressedAssetStore
from adjacency.imagine_signal.imagine_client import (
    EDIT_SURFACE,
    GENERATE_SURFACE,
    FixtureImagineClient,
    ImagineCallBudgetError,
    ImagineConfigurationError,
    ImagineResponseError,
    LiveImagineClient,
    RecordingImagineClient,
    build_imagine_client,
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
    ProviderCallState,
    ProviderOutcomeUnknownError,
    TransportImage,
    TransportResult,
)

pytestmark = pytest.mark.integration


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


def _generation(*, n: int = 1, prompt: str = "Synthetic product on blue"):
    return ImageGenerationRequest(
        schema_version="1.0",
        model="grok-imagine-image-2026-03-02",
        prompt=prompt,
        n=n,
    )


def _completed(*, n: int = 1, cost_ticks: int | None = 220_000_000):
    cost = CostMeasurement.unknown() if cost_ticks is None else CostMeasurement.known(cost_ticks)
    return TransportResult(
        state=ProviderCallState.COMPLETED,
        images=tuple(TransportImage(_png(channel=index)) for index in range(n)),
        provider_request_id="req_synthetic_1",
        provider_model_resolved="grok-imagine-image-2026-03-02",
        moderation_respected=True,
        cost=cost,
        latency_ms=420,
    )


class _Transport:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls: list[tuple[ImageOperation, object]] = []

    def invoke(self, *, operation, request):
        self.calls.append((operation, request))
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def _policy(*, max_calls: int = 1, max_outputs: int = 1, cost_cap: int = 1_000_000_000):
    return ExternalCallPolicy(
        approved=True,
        max_calls=max_calls,
        max_outputs_per_call=max_outputs,
        max_total_cost_ticks=cost_cap,
    )


def test_builder_defaults_to_replay_and_fixture_miss_never_constructs_transport(tmp_path):
    client = build_imagine_client(fixture_root=tmp_path)

    assert isinstance(client, FixtureImagineClient)
    with pytest.raises(BinaryFixtureMissError):
        client.generate(_generation())


def test_record_then_replay_is_byte_verified_and_transport_runs_once(tmp_path):
    fixture_store = BinaryFixtureStore(tmp_path)
    transport = _Transport(_completed())
    request = _generation()
    recorder = RecordingImagineClient(
        transport=transport,
        policy=_policy(),
        fixture_store=fixture_store,
    )

    recorded = recorder.generate(request)
    replayed = FixtureImagineClient(fixture_store).generate(request)

    assert recorded.mode == ImagineMode.RECORD
    assert replayed.mode == ImagineMode.REPLAY
    assert recorded.images[0].media_sha256 == replayed.images[0].media_sha256
    assert replayed.cost == CostMeasurement.known(220_000_000)
    assert replayed.budget_status == BudgetStatus.WITHIN_LIMIT
    assert transport.calls == [(ImageOperation.GENERATE, request)]
    assert fixture_store.fixture_path(GENERATE_SURFACE, request).is_file()


def test_edit_uses_distinct_surface_and_verified_reference_identity(tmp_path):
    store = BinaryFixtureStore(tmp_path)
    source_descriptor = store.asset_store.put(_png(channel=9)).descriptor
    request = ImageEditRequest(
        schema_version="1.0",
        model="grok-imagine-image-2026-03-02",
        prompt="Only make the background warmer",
        references=(
            ImageReference(
                media_sha256=source_descriptor.media_sha256,
                media_type=source_descriptor.content_type,
                width=source_descriptor.width,
                height=source_descriptor.height,
            ),
        ),
    )
    transport = _Transport(_completed())
    recorder = RecordingImagineClient(
        transport=transport,
        policy=_policy(),
        fixture_store=store,
    )

    result = recorder.edit(request)

    assert result.operation == ImageOperation.EDIT
    assert store.fixture_path(EDIT_SURFACE, request).is_file()


def test_external_modes_require_injected_transport_and_explicit_approval(tmp_path):
    with pytest.raises(ImagineConfigurationError, match="requires injected transport"):
        build_imagine_client(mode=ImagineMode.RECORD, fixture_root=tmp_path)
    with pytest.raises(ImagineConfigurationError, match="explicit approval"):
        RecordingImagineClient(
            transport=_Transport(_completed()),
            policy=ExternalCallPolicy(
                approved=False,
                max_total_cost_ticks=1,
            ),
            fixture_store=BinaryFixtureStore(tmp_path),
        )
    with pytest.raises(ImagineConfigurationError, match="positive cost cap"):
        RecordingImagineClient(
            transport=_Transport(_completed()),
            policy=ExternalCallPolicy(approved=True, max_total_cost_ticks=0),
            fixture_store=BinaryFixtureStore(tmp_path),
        )


def test_replay_mode_rejects_transport_objects(tmp_path):
    with pytest.raises(ImagineConfigurationError, match="cannot receive"):
        build_imagine_client(
            mode=ImagineMode.REPLAY,
            fixture_root=tmp_path,
            transport=_Transport(_completed()),
        )


def test_accept_then_timeout_returns_unknown_without_retry_and_blocks_next_call(tmp_path):
    transport = _Transport(
        ProviderOutcomeUnknownError("timed out after accept", provider_request_id="req_unknown")
    )
    client = RecordingImagineClient(
        transport=transport,
        policy=_policy(max_calls=2),
        fixture_store=BinaryFixtureStore(tmp_path),
    )

    result = client.generate(_generation())

    assert result.state == ProviderCallState.UNKNOWN
    assert result.error_code == "PROVIDER_OUTCOME_UNKNOWN"
    assert result.cost.status == CostStatus.UNKNOWN
    assert len(transport.calls) == 1
    with pytest.raises(ImagineCallBudgetError, match="unknown cost"):
        client.generate(_generation(prompt="second request"))
    assert len(transport.calls) == 1


def test_unknown_completed_cost_is_not_zero_and_blocks_further_calls(tmp_path):
    transport = _Transport(_completed(cost_ticks=None))
    client = RecordingImagineClient(
        transport=transport,
        policy=_policy(max_calls=2),
        fixture_store=BinaryFixtureStore(tmp_path),
    )

    result = client.generate(_generation())

    assert result.cost == CostMeasurement.unknown()
    assert result.cost.ticks is None
    assert result.budget_status == BudgetStatus.UNKNOWN
    with pytest.raises(ImagineCallBudgetError, match="unknown cost"):
        client.generate(_generation(prompt="blocked until reconciliation"))


def test_known_zero_cost_remains_distinct_from_unknown(tmp_path):
    client = RecordingImagineClient(
        transport=_Transport(_completed(cost_ticks=0)),
        policy=_policy(),
        fixture_store=BinaryFixtureStore(tmp_path),
    )

    result = client.generate(_generation())

    assert result.cost.status == CostStatus.KNOWN
    assert result.cost.ticks == 0
    assert result.budget_status == BudgetStatus.WITHIN_LIMIT


def test_actual_cost_overrun_is_returned_as_exceeded_and_stops_next_call(tmp_path):
    transport = _Transport(_completed(cost_ticks=11))
    client = RecordingImagineClient(
        transport=transport,
        policy=_policy(max_calls=2, cost_cap=10),
        fixture_store=BinaryFixtureStore(tmp_path),
    )

    result = client.generate(_generation())

    assert result.budget_status == BudgetStatus.EXCEEDED
    with pytest.raises(ImagineCallBudgetError, match="cost cap"):
        client.generate(_generation(prompt="no paid retry"))
    assert len(transport.calls) == 1


def test_request_and_response_output_counts_are_bounded(tmp_path):
    with pytest.raises(ValidationError):
        _generation(n=5)

    client = RecordingImagineClient(
        transport=_Transport(_completed(n=1)),
        policy=_policy(max_outputs=2),
        fixture_store=BinaryFixtureStore(tmp_path),
    )
    with pytest.raises(ImagineResponseError, match="expected 2 images"):
        client.generate(_generation(n=2))


def test_policy_output_cap_blocks_before_transport(tmp_path):
    transport = _Transport(_completed(n=2))
    client = RecordingImagineClient(
        transport=transport,
        policy=_policy(max_outputs=1),
        fixture_store=BinaryFixtureStore(tmp_path),
    )

    with pytest.raises(ImagineCallBudgetError, match="outputs"):
        client.generate(_generation(n=2))

    assert transport.calls == []


def test_typed_response_secret_is_scanned_before_fixture_or_blob_write(tmp_path):
    result = _completed()
    leaked = TransportResult(
        state=result.state,
        images=result.images,
        provider_request_id="Bearer not-recorded",
        provider_model_resolved=result.provider_model_resolved,
        moderation_respected=result.moderation_respected,
        cost=result.cost,
        latency_ms=result.latency_ms,
    )
    client = RecordingImagineClient(
        transport=_Transport(leaked),
        policy=_policy(),
        fixture_store=BinaryFixtureStore(tmp_path),
    )

    with pytest.raises(BinaryFixtureSecretError):
        client.generate(_generation())

    assert not (tmp_path / "api").exists()
    assert not (tmp_path / "assets").exists()


def test_live_request_secret_is_rejected_before_transport_or_storage(tmp_path):
    transport = _Transport(_completed())
    client = LiveImagineClient(
        transport=transport,
        policy=_policy(),
        asset_store=ContentAddressedAssetStore(tmp_path / "live-assets"),
    )

    with pytest.raises(BinaryFixtureSecretError):
        client.generate(_generation(prompt="Bearer not-sent"))

    assert transport.calls == []
    assert not (tmp_path / "live-assets").exists()


def test_unknown_outcome_identifier_is_secret_scanned(tmp_path):
    transport = _Transport(
        ProviderOutcomeUnknownError(
            "timed out after accept",
            provider_request_id="Bearer not-returned",
        )
    )
    client = RecordingImagineClient(
        transport=transport,
        policy=_policy(max_calls=2),
        fixture_store=BinaryFixtureStore(tmp_path),
    )

    with pytest.raises(BinaryFixtureSecretError):
        client.generate(_generation())

    assert len(transport.calls) == 1
    assert not (tmp_path / "api").exists()


def test_moderation_rejection_records_no_media_and_replays_terminal_state(tmp_path):
    result = TransportResult(
        state=ProviderCallState.MODERATION_REJECTED,
        images=(),
        provider_request_id="req_rejected",
        provider_model_resolved="grok-imagine-image-2026-03-02",
        moderation_respected=True,
        cost=CostMeasurement.known(0),
        latency_ms=10,
        error_code="PROVIDER_MODERATION_REJECTED",
    )
    store = BinaryFixtureStore(tmp_path)
    recorder = RecordingImagineClient(
        transport=_Transport(result),
        policy=_policy(),
        fixture_store=store,
    )

    recorded = recorder.generate(_generation())
    replayed = FixtureImagineClient(store).generate(_generation())

    assert recorded.state == ProviderCallState.MODERATION_REJECTED
    assert replayed.state == ProviderCallState.MODERATION_REJECTED
    assert replayed.images == ()


def test_live_mode_validates_to_explicit_store_without_recording_fixture(tmp_path):
    asset_store = ContentAddressedAssetStore(tmp_path / "live-assets")
    transport = _Transport(_completed())
    client = LiveImagineClient(
        transport=transport,
        policy=_policy(),
        asset_store=asset_store,
    )

    result = client.generate(_generation())

    assert result.mode == ImagineMode.LIVE
    assert result.images[0].blob_path.startswith(str(tmp_path / "live-assets"))
    assert not (tmp_path / "api").exists()


@pytest.mark.parametrize(
    ("result", "message"),
    [
        (replace(_completed(), provider_request_id=None), "request ID"),
        (replace(_completed(), provider_model_resolved=None), "resolved model"),
        (replace(_completed(), moderation_respected=None), "moderation disposition"),
        (replace(_completed(), latency_ms=None), "valid latency"),
        (replace(_completed(), error_code="IMPOSSIBLE"), "cannot carry an error"),
        (
            replace(
                _completed(),
                state=ProviderCallState.UNKNOWN,
                cost=CostMeasurement.known(1),
                images=(),
                error_code="UNKNOWN",
            ),
            "unknown outcome cannot carry known cost",
        ),
        (
            replace(
                _completed(),
                state=ProviderCallState.MODERATION_REJECTED,
                images=(TransportImage(_png()),),
                error_code="REJECTED",
            ),
            "non-completed response cannot contain media",
        ),
        (
            replace(
                _completed(),
                state=ProviderCallState.MODERATION_REJECTED,
                images=(),
                moderation_respected=False,
                error_code="REJECTED",
            ),
            "must confirm moderation",
        ),
        (
            replace(
                _completed(),
                state=ProviderCallState.MODERATION_REJECTED,
                images=(),
                moderation_respected=True,
                error_code=None,
            ),
            "requires an error code",
        ),
    ],
)
def test_malformed_transport_results_fail_before_fixture_admission(tmp_path, result, message):
    client = RecordingImagineClient(
        transport=_Transport(result),
        policy=_policy(),
        fixture_store=BinaryFixtureStore(tmp_path),
    )

    with pytest.raises(ImagineResponseError, match=message):
        client.generate(_generation())

    assert not (tmp_path / "api").exists()


def test_call_count_cap_blocks_a_second_external_invocation(tmp_path):
    transport = _Transport(_completed())
    client = LiveImagineClient(
        transport=transport,
        policy=_policy(max_calls=1),
        asset_store=ContentAddressedAssetStore(tmp_path / "live-assets"),
    )

    client.generate(_generation())
    with pytest.raises(ImagineCallBudgetError, match="call count"):
        client.generate(_generation(prompt="second"))

    assert len(transport.calls) == 1


def test_committed_synthetic_family_replays_offline_with_only_background_pixels_changed():
    repository_root = Path(__file__).resolve().parents[2]
    client = FixtureImagineClient(
        BinaryFixtureStore(repository_root / "fixtures" / "imagine_signal")
    )
    prompts = (
        "Fictional Orbit Bottle ad. Preserve the product, logo, composition, and text. "
        "Use the approved neutral background tone.",
        "Fictional Orbit Bottle ad. Preserve the product, logo, composition, and text. "
        "Change only background_tone. Set the background_tone to warm.",
        "Fictional Orbit Bottle ad. Preserve the product, logo, composition, and text. "
        "Change only background_tone. Set the background_tone to cool.",
    )
    results = tuple(client.generate(_generation(prompt=prompt)) for prompt in prompts)

    assert {result.response_origin for result in results} == {"SYNTHETIC_FIXTURE"}
    assert {result.generator_id for result in results} == {"imagine-signal-orbit-raster-v1"}
    assert {result.cost for result in results} == {CostMeasurement.known(0)}
    assert len({result.images[0].media_sha256 for result in results}) == 3
    assert {(result.images[0].width, result.images[0].height) for result in results} == {(192, 192)}

    pixel_sets = tuple(
        _decode_unfiltered_png(Path(result.images[0].blob_path)) for result in results
    )
    triplets = zip(*pixel_sets, strict=True)
    same_pixels = 0
    changed_pixels = 0
    for neutral, warm, cool in triplets:
        if neutral == warm == cool:
            same_pixels += 1
        else:
            assert (neutral, warm, cool) == (
                (154, 158, 166),
                (218, 142, 96),
                (91, 146, 214),
            )
            changed_pixels += 1
    assert same_pixels > 0
    assert changed_pixels > 0


def _decode_unfiltered_png(path: Path) -> tuple[tuple[int, int, int], ...]:
    media_bytes = path.read_bytes()
    position = 8
    compressed = bytearray()
    width = height = 0
    while position < len(media_bytes):
        length = struct.unpack(">I", media_bytes[position : position + 4])[0]
        chunk_type = media_bytes[position + 4 : position + 8]
        payload = media_bytes[position + 8 : position + 8 + length]
        if chunk_type == b"IHDR":
            width, height = struct.unpack(">II", payload[:8])
        if chunk_type == b"IDAT":
            compressed.extend(payload)
        position += 12 + length
    raw = zlib.decompress(bytes(compressed))
    rows = []
    row_width = width * 3
    for row_index in range(height):
        start = row_index * (row_width + 1)
        assert raw[start] == 0
        rows.extend(
            tuple(raw[offset : offset + 3]) for offset in range(start + 1, start + 1 + row_width, 3)
        )
    return tuple(rows)
