from __future__ import annotations

import binascii
import json
import struct
import zlib

import pytest

from adjacency.imagine_signal.adapters.fixture_blobs import (
    BinaryFixtureConflictError,
    BinaryFixtureCorruptError,
    BinaryFixtureMissError,
    BinaryFixtureSecretError,
    BinaryFixtureStore,
    metadata_sha256,
)
from adjacency.imagine_signal.ports import TransportImage

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


def _request(prompt: str = "Synthetic product on a blue background") -> dict[str, object]:
    return {
        "data_classification": "synthetic",
        "model": "grok-imagine-image-2026-03-02",
        "n": 1,
        "prompt": prompt,
    }


def _response(request_id: str = "req_fixture_1") -> dict[str, object]:
    return {
        "budget_status": "WITHIN_LIMIT",
        "cost": {"status": "KNOWN", "ticks": 220000000},
        "error_code": None,
        "generator_id": None,
        "latency_ms": 800,
        "moderation_respected": True,
        "provider_model_requested": "grok-imagine-image-2026-03-02",
        "provider_model_resolved": "grok-imagine-image-2026-03-02",
        "provider_request_id": request_id,
        "response_origin": "PROVIDER_RECORDING",
        "state": "COMPLETED",
    }


def test_record_then_replay_verifies_metadata_and_linked_asset(tmp_path):
    store = BinaryFixtureStore(tmp_path)
    media_bytes = _png()
    image = TransportImage(
        media_bytes,
        declared_content_type="image/png",
        declared_width=2,
        declared_height=2,
    )

    recorded = store.record(
        surface="imagine.images.generate",
        request=_request(),
        response_metadata=_response(),
        images=(image,),
    )
    replayed = store.replay(surface="imagine.images.generate", request=_request())

    assert replayed == recorded
    assert replayed.assets[0].path.endswith(f"{replayed.assets[0].descriptor.media_sha256}.png")
    document = json.loads(
        store.fixture_path("imagine.images.generate", _request()).read_text(encoding="utf-8")
    )
    assert "media_bytes" not in json.dumps(document)
    assert "b64_json" not in json.dumps(document)


def test_missing_fixture_is_terminal_and_request_changes_key(tmp_path):
    store = BinaryFixtureStore(tmp_path)

    assert store.fixture_path("imagine.images.generate", _request("one")) != store.fixture_path(
        "imagine.images.generate", _request("two")
    )
    with pytest.raises(BinaryFixtureMissError, match="fixture missing"):
        store.replay(surface="imagine.images.generate", request=_request())


@pytest.mark.parametrize(
    "request_metadata",
    [
        {"api_key": "secret"},
        {"nested": {"authorization": "hidden"}},
        {"prompt": "Bearer credential"},
        {"prompt": "https://example.invalid/private"},
    ],
)
def test_request_secrets_urls_and_credentials_are_rejected_before_write(tmp_path, request_metadata):
    store = BinaryFixtureStore(tmp_path)

    with pytest.raises(BinaryFixtureSecretError):
        store.record(
            surface="imagine.images.generate",
            request=request_metadata,
            response_metadata=_response(),
            images=(TransportImage(_png()),),
        )

    assert not (tmp_path / "assets").exists()


@pytest.mark.parametrize(
    "response",
    [
        {"authorization": "not-recorded"},
        {"nested": {"signed_url": "not-recorded"}},
        {"provider_request_id": "xai-secret-like"},
        {"provider_output": "data:image/png;base64,AAAA"},
        {"temporary": "https://example.invalid/output.png?signature=secret"},
    ],
)
def test_response_secrets_raw_media_and_urls_are_rejected_before_blob_write(tmp_path, response):
    store = BinaryFixtureStore(tmp_path)

    with pytest.raises(BinaryFixtureSecretError):
        store.record(
            surface="imagine.images.generate",
            request=_request(),
            response_metadata=response,
            images=(TransportImage(_png()),),
        )

    assert not (tmp_path / "assets").exists()


def test_fixture_metadata_tampering_is_rejected(tmp_path):
    store = BinaryFixtureStore(tmp_path)
    store.record(
        surface="imagine.images.generate",
        request=_request(),
        response_metadata=_response(),
        images=(TransportImage(_png()),),
    )
    path = store.fixture_path("imagine.images.generate", _request())
    document = json.loads(path.read_text(encoding="utf-8"))
    document["response_metadata"]["latency_ms"] = 1
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(BinaryFixtureCorruptError, match="response hash"):
        store.replay(surface="imagine.images.generate", request=_request())


def test_fixture_asset_declaration_tampering_is_rejected_even_with_rehashed_metadata(tmp_path):
    store = BinaryFixtureStore(tmp_path)
    store.record(
        surface="imagine.images.generate",
        request=_request(),
        response_metadata=_response(),
        images=(TransportImage(_png()),),
    )
    path = store.fixture_path("imagine.images.generate", _request())
    document = json.loads(path.read_text(encoding="utf-8"))
    document["assets"][0]["width"] = 999
    document["response_sha256"] = metadata_sha256(
        {
            "assets": document["assets"],
            "metadata": document["response_metadata"],
        }
    )
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(BinaryFixtureCorruptError, match="asset failed verification"):
        store.replay(surface="imagine.images.generate", request=_request())


def test_fixture_blob_tampering_is_rejected(tmp_path):
    store = BinaryFixtureStore(tmp_path)
    record = store.record(
        surface="imagine.images.generate",
        request=_request(),
        response_metadata=_response(),
        images=(TransportImage(_png(channel=1)),),
    )
    asset_path = record.assets[0].path
    with open(asset_path, "wb") as handle:
        handle.write(_png(channel=2))

    with pytest.raises(BinaryFixtureCorruptError, match="asset failed verification"):
        store.replay(surface="imagine.images.generate", request=_request())


def test_existing_request_fixture_is_immutable(tmp_path):
    store = BinaryFixtureStore(tmp_path)
    store.record(
        surface="imagine.images.generate",
        request=_request(),
        response_metadata=_response("req_original"),
        images=(TransportImage(_png(channel=1)),),
    )

    with pytest.raises(BinaryFixtureConflictError):
        store.record(
            surface="imagine.images.generate",
            request=_request(),
            response_metadata=_response("req_changed"),
            images=(TransportImage(_png(channel=2)),),
        )

    replayed = store.replay(surface="imagine.images.generate", request=_request())
    assert replayed.response_metadata["provider_request_id"] == "req_original"


def test_surface_rejects_path_traversal(tmp_path):
    store = BinaryFixtureStore(tmp_path)

    with pytest.raises(ValueError, match="surface"):
        store.request_hash("../outside", _request())


def test_response_allowlist_rejects_even_nonsecret_undeclared_fields(tmp_path):
    store = BinaryFixtureStore(tmp_path)
    response = _response() | {"debug_trace": "safe-looking but undeclared"}

    with pytest.raises(BinaryFixtureCorruptError, match="allowlist"):
        store.record(
            surface="imagine.images.generate",
            request=_request(),
            response_metadata=response,
            images=(TransportImage(_png()),),
        )


def test_record_fails_closed_when_existing_metadata_is_unreadable(tmp_path):
    store = BinaryFixtureStore(tmp_path)
    path = store.fixture_path("imagine.images.generate", _request())
    path.parent.mkdir(parents=True)
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(BinaryFixtureCorruptError, match="existing fixture"):
        store.record(
            surface="imagine.images.generate",
            request=_request(),
            response_metadata=_response(),
            images=(TransportImage(_png()),),
        )


def test_replay_fails_closed_when_metadata_is_unreadable(tmp_path):
    store = BinaryFixtureStore(tmp_path)
    path = store.fixture_path("imagine.images.generate", _request())
    path.parent.mkdir(parents=True)
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(BinaryFixtureCorruptError, match="cannot read fixture"):
        store.replay(surface="imagine.images.generate", request=_request())


def test_replay_rejects_undeclared_document_fields(tmp_path):
    store = BinaryFixtureStore(tmp_path)
    store.record(
        surface="imagine.images.generate",
        request=_request(),
        response_metadata=_response(),
        images=(TransportImage(_png()),),
    )
    path = store.fixture_path("imagine.images.generate", _request())
    document = json.loads(path.read_text(encoding="utf-8"))
    document["undeclared"] = True
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(BinaryFixtureCorruptError, match="invalid shape"):
        store.replay(surface="imagine.images.generate", request=_request())
