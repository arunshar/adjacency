"""Replay-first JSON metadata and digest-linked binary image fixtures."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from adjacency.imagine_signal.assets import (
    AssetDescriptor,
    ContentAddressedAssetStore,
    StoredAsset,
)
from adjacency.imagine_signal.ports import (
    FrozenAdapterModel,
    ImagineResponseMetadata,
    TransportImage,
)

FIXTURE_FORMAT_VERSION = 1
_SURFACE_PATTERN = re.compile(r"[a-z0-9][a-z0-9_.-]*\Z")
_SENSITIVE_KEYS = frozenset(
    {
        "access_token",
        "anthropic_api_key",
        "api_key",
        "authorization",
        "b64_json",
        "cookie",
        "image_url",
        "openai_api_key",
        "password",
        "refresh_token",
        "secret",
        "set_cookie",
        "signed_url",
        "token",
        "url",
        "xai_api_key",
    }
)
_SENSITIVE_VALUE_PREFIXES = (
    "bearer ",
    "data:image/",
    "sk-ant-",
    "sk-proj-",
    "xai-",
)
_SIGNED_QUERY_MARKERS = (
    "x-amz-credential=",
    "x-amz-signature=",
    "signature=",
    "sig=",
    "token=",
)
_ALLOWED_RESPONSE_KEYS = frozenset(
    {
        "budget_status",
        "cost",
        "error_code",
        "generator_id",
        "latency_ms",
        "moderation_respected",
        "provider_model_requested",
        "provider_model_resolved",
        "provider_request_id",
        "response_origin",
        "state",
    }
)


class BinaryFixtureError(RuntimeError):
    """Base error for binary fixture operations."""


class BinaryFixtureMissError(BinaryFixtureError, FileNotFoundError):
    """Replay could not find the exact canonical request."""


class BinaryFixtureCorruptError(BinaryFixtureError, ValueError):
    """Fixture metadata or linked media failed verification."""


class BinaryFixtureSecretError(BinaryFixtureError, ValueError):
    """Request or response metadata contains prohibited secret material."""


class BinaryFixtureConflictError(BinaryFixtureError):
    """A write attempted to change an immutable request fixture."""


class FixtureRecord(FrozenAdapterModel):
    """Verified fixture data returned to the replay client."""

    surface: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]*$")
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_metadata: dict[str, Any]
    assets: tuple[StoredAsset, ...]
    fixture_path: str = Field(min_length=1)


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _jsonable(value.model_dump(mode="json"))
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(value))
    if isinstance(value, Enum):
        return _jsonable(value.value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise TypeError(f"fixture values must be JSON-compatible, got {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Serialize fixture metadata in its byte-stable form."""

    return json.dumps(
        _jsonable(value),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def metadata_sha256(value: Any) -> str:
    """Hash canonical JSON metadata."""

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def reject_fixture_secrets(value: Any, *, path: str) -> None:
    """Recursively reject credential, raw media, and temporary URL material."""

    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized_key = str(key).strip().lower().replace("-", "_")
            if normalized_key in _SENSITIVE_KEYS:
                raise BinaryFixtureSecretError(f"prohibited field cannot be cached at {path}.{key}")
            reject_fixture_secrets(item, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            reject_fixture_secrets(item, path=f"{path}[{index}]")
        return
    if isinstance(value, str):
        normalized_value = value.strip().lower()
        if normalized_value.startswith(_SENSITIVE_VALUE_PREFIXES):
            raise BinaryFixtureSecretError(
                f"credential or raw-media value cannot be cached at {path}"
            )
        if normalized_value.startswith(("http://", "https://")):
            raise BinaryFixtureSecretError(f"URL cannot be cached at {path}")
        if any(marker in normalized_value for marker in _SIGNED_QUERY_MARKERS):
            raise BinaryFixtureSecretError(f"signed query material cannot be cached at {path}")


def _validate_response_allowlist(value: Any, *, fixture_path: Path | None = None) -> None:
    if not isinstance(value, dict) or set(value) != _ALLOWED_RESPONSE_KEYS:
        location = f": {fixture_path}" if fixture_path is not None else ""
        raise BinaryFixtureCorruptError(
            f"fixture response metadata does not match the allowlist{location}"
        )


class BinaryFixtureStore:
    """Content-addressed replay store for sanitized metadata and image blobs."""

    def __init__(
        self,
        root: Path | str = "fixtures/imagine_signal",
        *,
        asset_store: ContentAddressedAssetStore | None = None,
    ) -> None:
        self.root = Path(root)
        self.asset_store = asset_store or ContentAddressedAssetStore(self.root / "assets")

    @staticmethod
    def _validate_surface(surface: str) -> None:
        if not _SURFACE_PATTERN.fullmatch(surface):
            raise ValueError(
                "surface must start with a lowercase letter or digit and contain only "
                "lowercase letters, digits, dots, underscores, or hyphens"
            )

    def request_hash(self, surface: str, request: Any) -> str:
        """Return the canonical fixture identity after request secret scanning."""

        self._validate_surface(surface)
        normalized_request = _jsonable(request)
        reject_fixture_secrets(normalized_request, path="request")
        return metadata_sha256(
            {
                "format_version": FIXTURE_FORMAT_VERSION,
                "request": normalized_request,
                "surface": surface,
            }
        )

    def fixture_path(self, surface: str, request: Any) -> Path:
        """Resolve the immutable metadata path for a request."""

        return self.root / "api" / surface / f"{self.request_hash(surface, request)}.json"

    def record(
        self,
        *,
        surface: str,
        request: Any,
        response_metadata: Mapping[str, Any],
        images: Sequence[TransportImage],
    ) -> FixtureRecord:
        """Validate and atomically record one response and its linked media."""

        normalized_request = _jsonable(request)
        normalized_response = _jsonable(response_metadata)
        reject_fixture_secrets(normalized_request, path="request")
        reject_fixture_secrets(normalized_response, path="response")
        _validate_response_allowlist(normalized_response)
        try:
            normalized_response = ImagineResponseMetadata.model_validate(
                normalized_response
            ).model_dump(mode="json")
        except ValueError as error:
            raise BinaryFixtureCorruptError("fixture response metadata is invalid") from error
        path = self.fixture_path(surface, normalized_request)

        validated: list[tuple[TransportImage, AssetDescriptor]] = []
        for image in images:
            descriptor = self.asset_store.validate(
                image.media_bytes,
                declared_content_type=image.declared_content_type,
                declared_width=image.declared_width,
                declared_height=image.declared_height,
                expected_sha256=image.expected_sha256,
            )
            validated.append((image, descriptor))

        asset_documents = [descriptor.model_dump(mode="json") for _, descriptor in validated]
        response_sha256 = metadata_sha256(
            {"assets": asset_documents, "metadata": normalized_response}
        )
        document = {
            "assets": asset_documents,
            "format_version": FIXTURE_FORMAT_VERSION,
            "request": normalized_request,
            "request_sha256": path.stem,
            "response_metadata": normalized_response,
            "response_sha256": response_sha256,
            "surface": surface,
        }

        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise BinaryFixtureCorruptError(f"cannot read existing fixture {path}") from error
            if existing != document:
                raise BinaryFixtureConflictError(
                    f"fixture already exists with different response metadata: {path}"
                )

        stored_assets = tuple(
            self.asset_store.put(
                image.media_bytes,
                declared_content_type=descriptor.content_type,
                declared_width=descriptor.width,
                declared_height=descriptor.height,
                expected_sha256=descriptor.media_sha256,
                expected_byte_length=descriptor.byte_length,
            )
            for image, descriptor in validated
        )
        if not path.exists():
            self._write_atomic(path, document)
        return FixtureRecord(
            surface=surface,
            request_sha256=path.stem,
            response_sha256=response_sha256,
            response_metadata=normalized_response,
            assets=stored_assets,
            fixture_path=str(path),
        )

    def replay(self, *, surface: str, request: Any) -> FixtureRecord:
        """Replay the exact request, verifying metadata and every linked blob."""

        normalized_request = _jsonable(request)
        path = self.fixture_path(surface, normalized_request)
        if not path.is_file():
            raise BinaryFixtureMissError(f"fixture missing for {surface}: {path}")
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise BinaryFixtureCorruptError(f"cannot read fixture {path}: {error}") from error

        required = {
            "assets",
            "format_version",
            "request",
            "request_sha256",
            "response_metadata",
            "response_sha256",
            "surface",
        }
        if not isinstance(document, dict) or set(document) != required:
            raise BinaryFixtureCorruptError(f"fixture has an invalid shape: {path}")
        reject_fixture_secrets(document["request"], path="request")
        reject_fixture_secrets(document["response_metadata"], path="response")
        _validate_response_allowlist(document["response_metadata"], fixture_path=path)
        try:
            ImagineResponseMetadata.model_validate(document["response_metadata"])
        except ValueError as error:
            raise BinaryFixtureCorruptError(
                f"fixture response metadata is invalid: {path}"
            ) from error
        if document["format_version"] != FIXTURE_FORMAT_VERSION:
            raise BinaryFixtureCorruptError(f"fixture format version changed: {path}")
        if document["surface"] != surface or document["request"] != normalized_request:
            raise BinaryFixtureCorruptError(f"fixture request does not match its path: {path}")

        expected_request_hash = self.request_hash(surface, normalized_request)
        if (
            document["request_sha256"] != expected_request_hash
            or path.stem != expected_request_hash
        ):
            raise BinaryFixtureCorruptError(f"fixture request hash does not match: {path}")
        if not isinstance(document["assets"], list):
            raise BinaryFixtureCorruptError(f"fixture asset descriptors are not a list: {path}")
        if not isinstance(document["response_metadata"], dict):
            raise BinaryFixtureCorruptError(f"fixture response metadata is not an object: {path}")

        expected_response_hash = metadata_sha256(
            {
                "assets": document["assets"],
                "metadata": document["response_metadata"],
            }
        )
        if document["response_sha256"] != expected_response_hash:
            raise BinaryFixtureCorruptError(f"fixture response hash does not match: {path}")

        stored_assets: list[StoredAsset] = []
        for raw_descriptor in document["assets"]:
            try:
                descriptor = AssetDescriptor.model_validate(raw_descriptor)
                self.asset_store.read_verified(descriptor)
            except (ValueError, OSError) as error:
                raise BinaryFixtureCorruptError(
                    f"fixture asset failed verification: {path}: {error}"
                ) from error
            stored_assets.append(
                StoredAsset(descriptor=descriptor, path=str(self.asset_store.path_for(descriptor)))
            )

        return FixtureRecord(
            surface=surface,
            request_sha256=expected_request_hash,
            response_sha256=expected_response_hash,
            response_metadata=document["response_metadata"],
            assets=tuple(stored_assets),
            fixture_path=str(path),
        )

    @staticmethod
    def _write_atomic(path: Path, document: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                delete=False,
                dir=path.parent,
                encoding="utf-8",
                prefix=f".{path.stem}.",
                suffix=".tmp",
            ) as handle:
                temporary_path = Path(handle.name)
                json.dump(document, handle, ensure_ascii=True, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary_path, path)
            except FileExistsError as conflict:
                try:
                    existing = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as error:
                    raise BinaryFixtureCorruptError(
                        f"cannot read concurrently created fixture {path}"
                    ) from error
                if existing != document:
                    raise BinaryFixtureConflictError(
                        f"concurrent writer recorded a different response: {path}"
                    ) from conflict
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
