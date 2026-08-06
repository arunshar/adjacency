"""Content-addressed image validation and local blob persistence."""

from __future__ import annotations

import binascii
import hashlib
import os
import struct
import tempfile
from pathlib import Path

from pydantic import Field

from adjacency.imagine_signal.ports import FrozenAdapterModel

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_START = b"\xff\xd8"
_JPEG_SOF_MARKERS = frozenset(
    {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }
)


class AssetValidationError(ValueError):
    """Raised when untrusted media cannot be admitted."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


class AssetPolicy(FrozenAdapterModel):
    """Hard limits applied before media admission."""

    max_bytes: int = Field(default=20 * 1024 * 1024, gt=0)
    max_width: int = Field(default=8192, gt=0)
    max_height: int = Field(default=8192, gt=0)
    max_pixels: int = Field(default=8192 * 8192, gt=0)
    approved_content_types: tuple[str, ...] = ("image/png", "image/jpeg")


class AssetDescriptor(FrozenAdapterModel):
    """Immutable identity and verified shape for one media blob."""

    media_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_length: int = Field(gt=0)
    content_type: str = Field(pattern=r"^image/(png|jpeg)$")
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    extension: str = Field(pattern=r"^(png|jpg)$")


class StoredAsset(FrozenAdapterModel):
    """Verified descriptor plus its local durable path."""

    descriptor: AssetDescriptor
    path: str = Field(min_length=1)


def media_sha256(media_bytes: bytes) -> str:
    """Return the byte-exact SHA-256 digest for media."""

    return hashlib.sha256(media_bytes).hexdigest()


def _png_dimensions(media_bytes: bytes) -> tuple[int, int]:
    if len(media_bytes) < 33 or not media_bytes.startswith(PNG_SIGNATURE):
        raise AssetValidationError("ASSET_MALFORMED", "PNG signature or IHDR is missing")
    position = len(PNG_SIGNATURE)
    dimensions: tuple[int, int] | None = None
    saw_idat = False
    saw_iend = False
    while position < len(media_bytes):
        if position + 12 > len(media_bytes):
            raise AssetValidationError("ASSET_MALFORMED", "PNG chunk header is truncated")
        chunk_length = struct.unpack(">I", media_bytes[position : position + 4])[0]
        chunk_type = media_bytes[position + 4 : position + 8]
        chunk_end = position + 12 + chunk_length
        if chunk_end > len(media_bytes):
            raise AssetValidationError("ASSET_MALFORMED", "PNG chunk is truncated")
        payload = media_bytes[position + 8 : position + 8 + chunk_length]
        expected_crc = struct.unpack(">I", media_bytes[chunk_end - 4 : chunk_end])[0]
        actual_crc = binascii.crc32(chunk_type + payload) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise AssetValidationError("ASSET_MALFORMED", "PNG chunk checksum is invalid")
        if position == len(PNG_SIGNATURE):
            if chunk_type != b"IHDR" or chunk_length != 13:
                raise AssetValidationError("ASSET_MALFORMED", "PNG must start with a 13-byte IHDR")
            width, height = struct.unpack(">II", payload[:8])
            if width <= 0 or height <= 0:
                raise AssetValidationError("ASSET_MALFORMED", "PNG dimensions must be positive")
            dimensions = (width, height)
        elif chunk_type == b"IDAT":
            saw_idat = True
        elif chunk_type == b"IEND":
            if chunk_length != 0 or chunk_end != len(media_bytes):
                raise AssetValidationError("ASSET_MALFORMED", "PNG IEND is invalid")
            saw_iend = True
        position = chunk_end

    if dimensions is None or not saw_idat or not saw_iend:
        raise AssetValidationError("ASSET_MALFORMED", "PNG is missing required chunks")
    return dimensions


def _jpeg_dimensions(media_bytes: bytes) -> tuple[int, int]:
    if (
        len(media_bytes) < 4
        or not media_bytes.startswith(JPEG_START)
        or not media_bytes.endswith(b"\xff\xd9")
    ):
        raise AssetValidationError("ASSET_MALFORMED", "JPEG boundary marker is missing")

    position = 2
    while position < len(media_bytes):
        while position < len(media_bytes) and media_bytes[position] != 0xFF:
            position += 1
        while position < len(media_bytes) and media_bytes[position] == 0xFF:
            position += 1
        if position >= len(media_bytes):
            break

        marker = media_bytes[position]
        position += 1
        if marker in {0x01, 0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if position + 2 > len(media_bytes):
            raise AssetValidationError("ASSET_MALFORMED", "JPEG segment length is truncated")

        segment_length = struct.unpack(">H", media_bytes[position : position + 2])[0]
        if segment_length < 2 or position + segment_length > len(media_bytes):
            raise AssetValidationError("ASSET_MALFORMED", "JPEG segment is truncated")
        if marker in _JPEG_SOF_MARKERS:
            if segment_length < 7:
                raise AssetValidationError("ASSET_MALFORMED", "JPEG SOF segment is truncated")
            height, width = struct.unpack(">HH", media_bytes[position + 3 : position + 7])
            if width <= 0 or height <= 0:
                raise AssetValidationError("ASSET_MALFORMED", "JPEG dimensions must be positive")
            return width, height
        if marker == 0xDA:
            break
        position += segment_length

    raise AssetValidationError("ASSET_MALFORMED", "JPEG has no supported SOF marker")


def inspect_media(media_bytes: bytes) -> tuple[str, str, int, int]:
    """Identify an approved image using magic bytes and read its dimensions."""

    if media_bytes.startswith(PNG_SIGNATURE):
        width, height = _png_dimensions(media_bytes)
        return "image/png", "png", width, height
    if media_bytes.startswith(JPEG_START):
        width, height = _jpeg_dimensions(media_bytes)
        return "image/jpeg", "jpg", width, height
    raise AssetValidationError("ASSET_TYPE_UNSUPPORTED", "media magic bytes are not approved")


class ContentAddressedAssetStore:
    """Write-once local image store keyed by verified byte digest."""

    def __init__(self, root: Path | str, *, policy: AssetPolicy | None = None) -> None:
        self.root = Path(root)
        self.policy = policy or AssetPolicy()

    def validate(
        self,
        media_bytes: bytes,
        *,
        declared_content_type: str | None = None,
        declared_width: int | None = None,
        declared_height: int | None = None,
        expected_sha256: str | None = None,
        expected_byte_length: int | None = None,
    ) -> AssetDescriptor:
        """Validate bytes, declarations, dimensions, and digest without writing."""

        if not media_bytes:
            raise AssetValidationError("ASSET_EMPTY", "media contains no bytes")
        if len(media_bytes) > self.policy.max_bytes:
            raise AssetValidationError(
                "ASSET_TOO_LARGE",
                f"{len(media_bytes)} bytes exceeds {self.policy.max_bytes}",
            )
        content_type, extension, width, height = inspect_media(media_bytes)
        if content_type not in self.policy.approved_content_types:
            raise AssetValidationError(
                "ASSET_TYPE_UNSUPPORTED",
                f"{content_type} is not in the approved content-type set",
            )
        if declared_content_type is not None and declared_content_type != content_type:
            raise AssetValidationError(
                "ASSET_TYPE_MISMATCH",
                f"declared {declared_content_type}, detected {content_type}",
            )
        if declared_width is not None and declared_width != width:
            raise AssetValidationError(
                "ASSET_DIMENSION_MISMATCH",
                f"declared width {declared_width}, detected {width}",
            )
        if declared_height is not None and declared_height != height:
            raise AssetValidationError(
                "ASSET_DIMENSION_MISMATCH",
                f"declared height {declared_height}, detected {height}",
            )
        if (
            width > self.policy.max_width
            or height > self.policy.max_height
            or width * height > self.policy.max_pixels
        ):
            raise AssetValidationError(
                "ASSET_DIMENSIONS_EXCEEDED",
                f"detected dimensions {width}x{height} exceed policy",
            )

        digest = media_sha256(media_bytes)
        if expected_sha256 is not None and expected_sha256 != digest:
            raise AssetValidationError(
                "ASSET_HASH_MISMATCH",
                f"expected {expected_sha256}, detected {digest}",
            )
        if expected_byte_length is not None and expected_byte_length != len(media_bytes):
            raise AssetValidationError(
                "ASSET_LENGTH_MISMATCH",
                f"expected {expected_byte_length} bytes, detected {len(media_bytes)}",
            )
        return AssetDescriptor(
            media_sha256=digest,
            byte_length=len(media_bytes),
            content_type=content_type,
            width=width,
            height=height,
            extension=extension,
        )

    def path_for(self, descriptor: AssetDescriptor) -> Path:
        """Resolve a descriptor to its digest-derived path."""

        return self.root / f"{descriptor.media_sha256}.{descriptor.extension}"

    def put(
        self,
        media_bytes: bytes,
        *,
        declared_content_type: str | None = None,
        declared_width: int | None = None,
        declared_height: int | None = None,
        expected_sha256: str | None = None,
        expected_byte_length: int | None = None,
    ) -> StoredAsset:
        """Validate and persist one blob atomically."""

        descriptor = self.validate(
            media_bytes,
            declared_content_type=declared_content_type,
            declared_width=declared_width,
            declared_height=declared_height,
            expected_sha256=expected_sha256,
            expected_byte_length=expected_byte_length,
        )
        path = self.path_for(descriptor)
        if path.is_file():
            existing = path.read_bytes()
            self.validate(
                existing,
                declared_content_type=descriptor.content_type,
                declared_width=descriptor.width,
                declared_height=descriptor.height,
                expected_sha256=descriptor.media_sha256,
                expected_byte_length=descriptor.byte_length,
            )
            return StoredAsset(descriptor=descriptor, path=str(path))

        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "wb",
                delete=False,
                dir=path.parent,
                prefix=f".{descriptor.media_sha256}.",
                suffix=".tmp",
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(media_bytes)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
        return StoredAsset(descriptor=descriptor, path=str(path))

    def read_verified(self, descriptor: AssetDescriptor) -> bytes:
        """Read a stored blob and recheck every declared property."""

        path = self.path_for(descriptor)
        if not path.is_file():
            raise AssetValidationError("ASSET_MISSING", f"blob is missing at {path}")
        media_bytes = path.read_bytes()
        actual = self.validate(
            media_bytes,
            declared_content_type=descriptor.content_type,
            declared_width=descriptor.width,
            declared_height=descriptor.height,
            expected_sha256=descriptor.media_sha256,
            expected_byte_length=descriptor.byte_length,
        )
        if actual.extension != descriptor.extension:
            raise AssetValidationError(
                "ASSET_TYPE_MISMATCH",
                f"declared extension {descriptor.extension}, detected {actual.extension}",
            )
        return media_bytes
