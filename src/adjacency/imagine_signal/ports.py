"""Provider-independent contracts for the Imagine boundary.

The module deliberately contains no HTTP client, credential lookup, or environment
switch. Replay, recording, and live execution are selected explicitly by callers.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_OUTPUTS_PER_CALL = 4
MAX_REFERENCE_IMAGES = 3


class ImagineMode(StrEnum):
    """Execution modes ordered by increasing external effect."""

    REPLAY = "replay"
    RECORD = "record"
    LIVE = "live"


class ImageOperation(StrEnum):
    """Semantic operations exposed by the provider-independent client."""

    GENERATE = "generate"
    EDIT = "edit"


class ProviderCallState(StrEnum):
    """Normalized provider completion state."""

    COMPLETED = "COMPLETED"
    MODERATION_REJECTED = "MODERATION_REJECTED"
    UNKNOWN = "UNKNOWN"


class ResponseOrigin(StrEnum):
    """How normalized response evidence was produced."""

    SYNTHETIC_FIXTURE = "SYNTHETIC_FIXTURE"
    PROVIDER_RECORDING = "PROVIDER_RECORDING"
    LIVE_PROVIDER = "LIVE_PROVIDER"


class CostStatus(StrEnum):
    """Whether provider cost is an exact reported value."""

    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"


class BudgetStatus(StrEnum):
    """Post-call cost admission state."""

    WITHIN_LIMIT = "WITHIN_LIMIT"
    EXCEEDED = "EXCEEDED"
    UNKNOWN = "UNKNOWN"


class FrozenAdapterModel(BaseModel):
    """Immutable, closed model used only at the Imagine adapter boundary."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class CostMeasurement(FrozenAdapterModel):
    """Exact integer ticks or an explicit unknown value.

    Zero is valid only when the provider explicitly reports zero ticks.
    """

    status: CostStatus
    ticks: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _status_matches_ticks(self) -> CostMeasurement:
        if self.status == CostStatus.KNOWN and self.ticks is None:
            raise ValueError("known cost requires integer ticks")
        if self.status == CostStatus.UNKNOWN and self.ticks is not None:
            raise ValueError("unknown cost cannot carry ticks")
        return self

    @classmethod
    def known(cls, ticks: int) -> CostMeasurement:
        return cls(status=CostStatus.KNOWN, ticks=ticks)

    @classmethod
    def unknown(cls) -> CostMeasurement:
        return cls(status=CostStatus.UNKNOWN, ticks=None)


class ImageReference(FrozenAdapterModel):
    """Verified input-media identity for an edit request."""

    media_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    media_type: str = Field(pattern=r"^image/(png|jpeg)$")
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    provider_file_id: str | None = Field(default=None, min_length=1)


class _ImageRequest(FrozenAdapterModel):
    schema_version: str = Field(min_length=1)
    model: str = Field(min_length=1)
    prompt: str = Field(min_length=1, max_length=20_000)
    n: int = Field(default=1, ge=1, le=MAX_OUTPUTS_PER_CALL)
    aspect_ratio: str = Field(default="1:1", min_length=1)
    resolution: str = Field(default="1k", pattern=r"^(1k|2k)$")
    data_classification: str = Field(
        default="synthetic",
        pattern=r"^(synthetic|non_sensitive_demo)$",
    )

    @field_validator("model", "prompt", "aspect_ratio")
    @classmethod
    def _normalize_text(cls, value: str) -> str:
        normalized = unicodedata.normalize("NFC", value).strip()
        if not normalized:
            raise ValueError("text fields cannot be blank")
        return normalized


class ImageGenerationRequest(_ImageRequest):
    """A bounded text-to-image request."""


class ImageEditRequest(_ImageRequest):
    """A bounded edit request referencing already verified inputs."""

    references: tuple[ImageReference, ...] = Field(
        min_length=1,
        max_length=MAX_REFERENCE_IMAGES,
    )


ImagineRequest = ImageGenerationRequest | ImageEditRequest


class GeneratedImage(FrozenAdapterModel):
    """Verified durable media identity returned to the application."""

    ordinal: int = Field(ge=0)
    media_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    media_type: str = Field(pattern=r"^image/(png|jpeg)$")
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    byte_length: int = Field(gt=0)
    blob_path: str = Field(min_length=1)


class ImagineResponseMetadata(FrozenAdapterModel):
    """Strict response fields permitted in a replay fixture."""

    state: ProviderCallState
    response_origin: ResponseOrigin
    generator_id: str | None = Field(default=None, min_length=1)
    provider_request_id: str | None = Field(default=None, min_length=1)
    provider_model_requested: str = Field(min_length=1)
    provider_model_resolved: str | None = Field(default=None, min_length=1)
    moderation_respected: bool | None = None
    cost: CostMeasurement
    budget_status: BudgetStatus
    latency_ms: int | None = Field(default=None, ge=0)
    error_code: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _origin_has_provenance(self) -> ImagineResponseMetadata:
        if self.response_origin == ResponseOrigin.SYNTHETIC_FIXTURE and self.generator_id is None:
            raise ValueError("synthetic fixture response requires a generator ID")
        return self


class ImagineCallResult(FrozenAdapterModel):
    """Normalized call result for replay, recording, or live execution."""

    mode: ImagineMode
    operation: ImageOperation
    state: ProviderCallState
    response_origin: ResponseOrigin
    generator_id: str | None = Field(default=None, min_length=1)
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    response_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    provider_request_id: str | None = Field(default=None, min_length=1)
    provider_model_requested: str = Field(min_length=1)
    provider_model_resolved: str | None = Field(default=None, min_length=1)
    moderation_respected: bool | None = None
    cost: CostMeasurement
    budget_status: BudgetStatus
    latency_ms: int | None = Field(default=None, ge=0)
    images: tuple[GeneratedImage, ...] = ()
    error_code: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _completion_shape(self) -> ImagineCallResult:
        if self.response_origin == ResponseOrigin.SYNTHETIC_FIXTURE and self.generator_id is None:
            raise ValueError("synthetic fixture response requires a generator ID")
        if self.state == ProviderCallState.COMPLETED and not self.images:
            raise ValueError("completed call requires at least one verified image")
        if self.state != ProviderCallState.COMPLETED and self.images:
            raise ValueError("non-completed call cannot admit images")
        if self.state == ProviderCallState.UNKNOWN:
            if self.error_code is None:
                raise ValueError("unknown call requires an error code")
            if self.cost.status != CostStatus.UNKNOWN:
                raise ValueError("unknown call outcome requires unknown cost")
        return self


class ExternalCallPolicy(FrozenAdapterModel):
    """Explicit, bounded authorization required for any external invocation."""

    approved: bool = False
    max_calls: int = Field(default=1, ge=1, le=100)
    max_outputs_per_call: int = Field(default=1, ge=1, le=MAX_OUTPUTS_PER_CALL)
    max_total_cost_ticks: int = Field(ge=0)


@dataclass(frozen=True, slots=True)
class TransportImage:
    """Downloaded or decoded provider media awaiting validation."""

    media_bytes: bytes
    declared_content_type: str | None = None
    declared_width: int | None = None
    declared_height: int | None = None
    expected_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class TransportResult:
    """Typed result returned by an injected provider transport."""

    state: ProviderCallState
    images: tuple[TransportImage, ...] = ()
    provider_request_id: str | None = None
    provider_model_resolved: str | None = None
    moderation_respected: bool | None = None
    cost: CostMeasurement = CostMeasurement(status=CostStatus.UNKNOWN)
    latency_ms: int | None = None
    error_code: str | None = None


class ProviderOutcomeUnknownError(RuntimeError):
    """The provider may have accepted work, but completion cannot be reconciled."""

    def __init__(self, message: str, *, provider_request_id: str | None = None) -> None:
        super().__init__(message)
        self.provider_request_id = provider_request_id


class ImagineTransport(Protocol):
    """Injected transport that performs exactly one provider operation."""

    def invoke(
        self,
        *,
        operation: ImageOperation,
        request: ImagineRequest,
    ) -> TransportResult:
        """Invoke once. Retry and fallback are intentionally absent."""


class ImagineClient(Protocol):
    """Provider-independent image generation interface."""

    def generate(self, request: ImageGenerationRequest) -> ImagineCallResult:
        """Generate or replay images."""

    def edit(self, request: ImageEditRequest) -> ImagineCallResult:
        """Edit or replay images."""
