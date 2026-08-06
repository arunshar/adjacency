from __future__ import annotations

import binascii
import hashlib
import struct
import zlib

import pytest

from adjacency.imagine_signal.assets import (
    AssetPolicy,
    AssetValidationError,
    ContentAddressedAssetStore,
)

pytestmark = pytest.mark.unit


def _png(width: int = 2, height: int = 3, *, channel: int = 0) -> bytes:
    def chunk(name: bytes, payload: bytes) -> bytes:
        checksum = binascii.crc32(name + payload) & 0xFFFFFFFF
        return struct.pack(">I", len(payload)) + name + payload + struct.pack(">I", checksum)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = bytes([0]) + bytes([channel, 40, 80]) * width
    pixels = row * height
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(pixels))
        + chunk(b"IEND", b"")
    )


def _jpeg(width: int = 5, height: int = 7) -> bytes:
    sof = bytes([8]) + struct.pack(">HH", height, width) + bytes([1, 1, 0x11, 0])
    return b"\xff\xd8\xff\xc0" + struct.pack(">H", len(sof) + 2) + sof + b"\xff\xd9"


@pytest.mark.parametrize(
    ("media_bytes", "content_type", "extension", "dimensions"),
    [
        (_png(), "image/png", "png", (2, 3)),
        (_jpeg(), "image/jpeg", "jpg", (5, 7)),
    ],
)
def test_store_round_trip_verifies_type_dimensions_length_and_digest(
    tmp_path, media_bytes, content_type, extension, dimensions
):
    store = ContentAddressedAssetStore(tmp_path)
    digest = hashlib.sha256(media_bytes).hexdigest()

    stored = store.put(
        media_bytes,
        declared_content_type=content_type,
        declared_width=dimensions[0],
        declared_height=dimensions[1],
        expected_sha256=digest,
        expected_byte_length=len(media_bytes),
    )

    assert stored.descriptor.media_sha256 == digest
    assert stored.descriptor.extension == extension
    assert store.read_verified(stored.descriptor) == media_bytes
    assert store.put(media_bytes) == stored


@pytest.mark.parametrize(
    ("declaration", "value", "code"),
    [
        ("declared_content_type", "image/jpeg", "ASSET_TYPE_MISMATCH"),
        ("declared_width", 99, "ASSET_DIMENSION_MISMATCH"),
        ("declared_height", 99, "ASSET_DIMENSION_MISMATCH"),
        ("expected_sha256", "0" * 64, "ASSET_HASH_MISMATCH"),
        ("expected_byte_length", 1, "ASSET_LENGTH_MISMATCH"),
    ],
)
def test_validate_rejects_false_declarations(tmp_path, declaration, value, code):
    store = ContentAddressedAssetStore(tmp_path)

    with pytest.raises(AssetValidationError) as caught:
        store.validate(_png(), **{declaration: value})

    assert caught.value.code == code


def test_validate_enforces_byte_and_dimension_caps(tmp_path):
    media_bytes = _png(width=4, height=3)

    with pytest.raises(AssetValidationError) as too_large:
        ContentAddressedAssetStore(
            tmp_path / "bytes", policy=AssetPolicy(max_bytes=len(media_bytes) - 1)
        ).validate(media_bytes)
    with pytest.raises(AssetValidationError) as too_wide:
        ContentAddressedAssetStore(tmp_path / "width", policy=AssetPolicy(max_width=3)).validate(
            media_bytes
        )
    with pytest.raises(AssetValidationError) as too_many_pixels:
        ContentAddressedAssetStore(tmp_path / "pixels", policy=AssetPolicy(max_pixels=11)).validate(
            media_bytes
        )

    assert too_large.value.code == "ASSET_TOO_LARGE"
    assert too_wide.value.code == "ASSET_DIMENSIONS_EXCEEDED"
    assert too_many_pixels.value.code == "ASSET_DIMENSIONS_EXCEEDED"


@pytest.mark.parametrize(
    "media_bytes",
    [b"", b"not an image", b"\x89PNG\r\n\x1a\ntruncated", b"\xff\xd8\xff\xc0\x00"],
)
def test_validate_rejects_empty_unsupported_or_truncated_media(tmp_path, media_bytes):
    store = ContentAddressedAssetStore(tmp_path)

    with pytest.raises(AssetValidationError):
        store.validate(media_bytes)


def test_read_verified_rejects_blob_tampering(tmp_path):
    store = ContentAddressedAssetStore(tmp_path)
    stored = store.put(_png(channel=10))
    path = store.path_for(stored.descriptor)
    path.write_bytes(_png(channel=20))

    with pytest.raises(AssetValidationError) as caught:
        store.read_verified(stored.descriptor)

    assert caught.value.code == "ASSET_HASH_MISMATCH"


def test_read_verified_rejects_missing_blob(tmp_path):
    store = ContentAddressedAssetStore(tmp_path)
    descriptor = store.validate(_png())

    with pytest.raises(AssetValidationError) as caught:
        store.read_verified(descriptor)

    assert caught.value.code == "ASSET_MISSING"


@pytest.mark.parametrize(
    "media_bytes",
    [
        _png()[:-12],
        _png()[:33],
        _png()[:-1] + bytes([_png()[-1] ^ 1]),
        _jpeg()[:-2],
    ],
)
def test_structurally_incomplete_or_checksum_corrupt_media_is_rejected(tmp_path, media_bytes):
    with pytest.raises(AssetValidationError) as caught:
        ContentAddressedAssetStore(tmp_path).validate(media_bytes)

    assert caught.value.code == "ASSET_MALFORMED"


def test_policy_can_disable_an_otherwise_detected_media_type(tmp_path):
    store = ContentAddressedAssetStore(
        tmp_path,
        policy=AssetPolicy(approved_content_types=("image/jpeg",)),
    )

    with pytest.raises(AssetValidationError) as caught:
        store.validate(_png())

    assert caught.value.code == "ASSET_TYPE_UNSUPPORTED"


def test_read_verified_rejects_extension_identity_mismatch(tmp_path):
    store = ContentAddressedAssetStore(tmp_path)
    descriptor = store.validate(_png())
    false_descriptor = descriptor.model_copy(update={"extension": "jpg"})
    store.path_for(false_descriptor).parent.mkdir(parents=True, exist_ok=True)
    store.path_for(false_descriptor).write_bytes(_png())

    with pytest.raises(AssetValidationError) as caught:
        store.read_verified(false_descriptor)

    assert caught.value.code == "ASSET_TYPE_MISMATCH"
