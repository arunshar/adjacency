"""Replay-first Grok Imagine client with explicit external-call authorization."""

from __future__ import annotations

import threading
from pathlib import Path

from adjacency.imagine_signal.adapters.fixture_blobs import (
    BinaryFixtureStore,
    FixtureRecord,
    metadata_sha256,
    reject_fixture_secrets,
)
from adjacency.imagine_signal.assets import ContentAddressedAssetStore, StoredAsset
from adjacency.imagine_signal.ports import (
    BudgetStatus,
    CostMeasurement,
    CostStatus,
    ExternalCallPolicy,
    GeneratedImage,
    ImageEditRequest,
    ImageGenerationRequest,
    ImageOperation,
    ImagineCallResult,
    ImagineClient,
    ImagineMode,
    ImagineRequest,
    ImagineResponseMetadata,
    ImagineTransport,
    ProviderCallState,
    ProviderOutcomeUnknownError,
    ResponseOrigin,
    TransportImage,
    TransportResult,
)

GENERATE_SURFACE = "imagine.images.generate"
EDIT_SURFACE = "imagine.images.edit"


class ImagineClientError(RuntimeError):
    """Base error for Imagine adapter failures."""


class ImagineConfigurationError(ImagineClientError):
    """Client mode or external authorization is invalid."""


class ImagineResponseError(ImagineClientError):
    """Provider response does not satisfy the normalized contract."""


class ImagineCallBudgetError(ImagineClientError):
    """No further external call is permitted by the configured budget."""


def _surface(operation: ImageOperation) -> str:
    return GENERATE_SURFACE if operation == ImageOperation.GENERATE else EDIT_SURFACE


def _generated_images(assets: tuple[StoredAsset, ...]) -> tuple[GeneratedImage, ...]:
    return tuple(
        GeneratedImage(
            ordinal=ordinal,
            media_sha256=asset.descriptor.media_sha256,
            media_type=asset.descriptor.content_type,
            width=asset.descriptor.width,
            height=asset.descriptor.height,
            byte_length=asset.descriptor.byte_length,
            blob_path=asset.path,
        )
        for ordinal, asset in enumerate(assets)
    )


def _result_from_record(
    *,
    mode: ImagineMode,
    operation: ImageOperation,
    request: ImagineRequest,
    record: FixtureRecord,
) -> ImagineCallResult:
    try:
        metadata = ImagineResponseMetadata.model_validate(record.response_metadata)
    except ValueError as error:
        raise ImagineResponseError("fixture response metadata is invalid") from error
    images = _generated_images(record.assets)
    if metadata.state == ProviderCallState.COMPLETED and len(images) != request.n:
        raise ImagineResponseError(
            f"completed response expected {request.n} images, received {len(images)}"
        )
    if metadata.state != ProviderCallState.COMPLETED and images:
        raise ImagineResponseError("non-completed response contains admitted images")
    return ImagineCallResult(
        mode=mode,
        operation=operation,
        state=metadata.state,
        response_origin=metadata.response_origin,
        generator_id=metadata.generator_id,
        request_sha256=record.request_sha256,
        response_sha256=record.response_sha256,
        provider_request_id=metadata.provider_request_id,
        provider_model_requested=metadata.provider_model_requested,
        provider_model_resolved=metadata.provider_model_resolved,
        moderation_respected=metadata.moderation_respected,
        cost=metadata.cost,
        budget_status=metadata.budget_status,
        latency_ms=metadata.latency_ms,
        images=images,
        error_code=metadata.error_code,
    )


class FixtureImagineClient:
    """Credential-free client that only replays exact committed fixtures."""

    mode = ImagineMode.REPLAY

    def __init__(self, fixture_store: BinaryFixtureStore | None = None) -> None:
        self.fixture_store = fixture_store or BinaryFixtureStore()

    def generate(self, request: ImageGenerationRequest) -> ImagineCallResult:
        return self._replay(ImageOperation.GENERATE, request)

    def edit(self, request: ImageEditRequest) -> ImagineCallResult:
        return self._replay(ImageOperation.EDIT, request)

    def _replay(self, operation: ImageOperation, request: ImagineRequest) -> ImagineCallResult:
        record = self.fixture_store.replay(surface=_surface(operation), request=request)
        return _result_from_record(
            mode=self.mode,
            operation=operation,
            request=request,
            record=record,
        )


class _ExternalImagineClient:
    """Single-provider client with bounded calls and no retry or fallback path."""

    def __init__(
        self,
        *,
        mode: ImagineMode,
        transport: ImagineTransport,
        policy: ExternalCallPolicy,
        fixture_store: BinaryFixtureStore | None = None,
        asset_store: ContentAddressedAssetStore | None = None,
    ) -> None:
        if mode not in {ImagineMode.RECORD, ImagineMode.LIVE}:
            raise ImagineConfigurationError("external client mode must be record or live")
        if not policy.approved:
            raise ImagineConfigurationError("external calls require explicit approval")
        if policy.max_total_cost_ticks == 0:
            raise ImagineConfigurationError("external calls require a positive cost cap")
        if mode == ImagineMode.RECORD and fixture_store is None:
            raise ImagineConfigurationError("record mode requires a binary fixture store")
        if mode == ImagineMode.LIVE and asset_store is None:
            raise ImagineConfigurationError("live mode requires an explicit asset store")

        self.mode = mode
        self.transport = transport
        self.policy = policy
        self.fixture_store = fixture_store
        self.asset_store = asset_store
        self._calls_used = 0
        self._known_spend_ticks = 0
        self._cost_reconciliation_blocked = False
        self._lock = threading.Lock()

    def generate(self, request: ImageGenerationRequest) -> ImagineCallResult:
        return self._invoke(ImageOperation.GENERATE, request)

    def edit(self, request: ImageEditRequest) -> ImagineCallResult:
        return self._invoke(ImageOperation.EDIT, request)

    def _admit_call(self, request: ImagineRequest) -> None:
        with self._lock:
            if self._cost_reconciliation_blocked:
                raise ImagineCallBudgetError(
                    "external calls are blocked until unknown cost is reconciled"
                )
            if self._calls_used >= self.policy.max_calls:
                raise ImagineCallBudgetError("external call count cap is exhausted")
            if self._known_spend_ticks >= self.policy.max_total_cost_ticks:
                raise ImagineCallBudgetError("external cost cap is exhausted")
            if request.n > self.policy.max_outputs_per_call:
                raise ImagineCallBudgetError(
                    f"request asks for {request.n} outputs, cap is "
                    f"{self.policy.max_outputs_per_call}"
                )
            self._calls_used += 1

    def _cost_status(self, cost: CostMeasurement) -> BudgetStatus:
        with self._lock:
            if cost.status == CostStatus.UNKNOWN:
                self._cost_reconciliation_blocked = True
                return BudgetStatus.UNKNOWN
            if cost.ticks is None:
                raise ImagineResponseError("known provider cost is missing ticks")
            self._known_spend_ticks += cost.ticks
            if self._known_spend_ticks > self.policy.max_total_cost_ticks:
                return BudgetStatus.EXCEEDED
            return BudgetStatus.WITHIN_LIMIT

    def _invoke(self, operation: ImageOperation, request: ImagineRequest) -> ImagineCallResult:
        reject_fixture_secrets(request.model_dump(mode="json"), path="request")
        self._admit_call(request)
        surface = _surface(operation)
        if self.fixture_store is None and self.asset_store is None:
            raise ImagineConfigurationError("external client has no configured storage")
        request_hash = (
            self.fixture_store.request_hash(surface, request)
            if self.fixture_store is not None
            else metadata_sha256(
                {
                    "format_version": 1,
                    "request": request.model_dump(mode="json"),
                    "surface": surface,
                }
            )
        )
        try:
            transport_result = self.transport.invoke(operation=operation, request=request)
        except ProviderOutcomeUnknownError as error:
            self._cost_status(CostMeasurement.unknown())
            reject_fixture_secrets(
                {"provider_request_id": error.provider_request_id},
                path="response",
            )
            return ImagineCallResult(
                mode=self.mode,
                operation=operation,
                state=ProviderCallState.UNKNOWN,
                response_origin=(
                    ResponseOrigin.PROVIDER_RECORDING
                    if self.mode == ImagineMode.RECORD
                    else ResponseOrigin.LIVE_PROVIDER
                ),
                generator_id=None,
                request_sha256=request_hash,
                response_sha256=None,
                provider_request_id=error.provider_request_id,
                provider_model_requested=request.model,
                provider_model_resolved=None,
                moderation_respected=None,
                cost=CostMeasurement.unknown(),
                budget_status=BudgetStatus.UNKNOWN,
                latency_ms=None,
                images=(),
                error_code="PROVIDER_OUTCOME_UNKNOWN",
            )

        self._validate_transport_result(transport_result, request)
        budget_status = self._cost_status(transport_result.cost)
        response_metadata = ImagineResponseMetadata(
            state=transport_result.state,
            response_origin=(
                ResponseOrigin.PROVIDER_RECORDING
                if self.mode == ImagineMode.RECORD
                else ResponseOrigin.LIVE_PROVIDER
            ),
            generator_id=None,
            provider_request_id=transport_result.provider_request_id,
            provider_model_requested=request.model,
            provider_model_resolved=transport_result.provider_model_resolved,
            moderation_respected=transport_result.moderation_respected,
            cost=transport_result.cost,
            budget_status=budget_status,
            latency_ms=transport_result.latency_ms,
            error_code=transport_result.error_code,
        )
        normalized_metadata = response_metadata.model_dump(mode="json")
        reject_fixture_secrets(normalized_metadata, path="response")

        if self.mode == ImagineMode.RECORD:
            if self.fixture_store is None:
                raise ImagineConfigurationError("record client has no fixture store")
            record = self.fixture_store.record(
                surface=surface,
                request=request,
                response_metadata=normalized_metadata,
                images=transport_result.images,
            )
            return _result_from_record(
                mode=self.mode,
                operation=operation,
                request=request,
                record=record,
            )

        if self.asset_store is None:
            raise ImagineConfigurationError("live client has no asset store")
        assets = self._store_live_assets(transport_result.images)
        response_hash = metadata_sha256(
            {
                "assets": [asset.descriptor.model_dump(mode="json") for asset in assets],
                "metadata": normalized_metadata,
            }
        )
        return ImagineCallResult(
            mode=self.mode,
            operation=operation,
            state=transport_result.state,
            response_origin=response_metadata.response_origin,
            generator_id=response_metadata.generator_id,
            request_sha256=request_hash,
            response_sha256=response_hash,
            provider_request_id=response_metadata.provider_request_id,
            provider_model_requested=response_metadata.provider_model_requested,
            provider_model_resolved=response_metadata.provider_model_resolved,
            moderation_respected=response_metadata.moderation_respected,
            cost=response_metadata.cost,
            budget_status=response_metadata.budget_status,
            latency_ms=response_metadata.latency_ms,
            images=_generated_images(assets),
            error_code=response_metadata.error_code,
        )

    @staticmethod
    def _validate_transport_result(result: TransportResult, request: ImagineRequest) -> None:
        if result.state == ProviderCallState.COMPLETED:
            if len(result.images) != request.n:
                raise ImagineResponseError(
                    f"completed response expected {request.n} images, received {len(result.images)}"
                )
            if result.provider_request_id is None:
                raise ImagineResponseError("completed response has no provider request ID")
            if result.provider_model_resolved is None:
                raise ImagineResponseError("completed response has no resolved model")
            if result.moderation_respected is None:
                raise ImagineResponseError("completed response has no moderation disposition")
            if result.latency_ms is None or result.latency_ms < 0:
                raise ImagineResponseError("completed response has no valid latency")
            if result.error_code is not None:
                raise ImagineResponseError("completed response cannot carry an error code")
            return
        if result.images:
            raise ImagineResponseError("non-completed response cannot contain media")
        if result.state == ProviderCallState.UNKNOWN:
            if result.cost.status != CostStatus.UNKNOWN:
                raise ImagineResponseError("unknown outcome cannot carry known cost")
            if result.error_code is None:
                raise ImagineResponseError("unknown outcome requires an error code")
        if result.state == ProviderCallState.MODERATION_REJECTED:
            if result.moderation_respected is not True:
                raise ImagineResponseError(
                    "moderation-rejected response must confirm moderation was respected"
                )
            if result.error_code is None:
                raise ImagineResponseError("moderation rejection requires an error code")

    def _store_live_assets(self, images: tuple[TransportImage, ...]) -> tuple[StoredAsset, ...]:
        if self.asset_store is None:
            raise ImagineConfigurationError("live client has no asset store")
        validated = tuple(
            (
                image,
                self.asset_store.validate(
                    image.media_bytes,
                    declared_content_type=image.declared_content_type,
                    declared_width=image.declared_width,
                    declared_height=image.declared_height,
                    expected_sha256=image.expected_sha256,
                ),
            )
            for image in images
        )
        return tuple(
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


class RecordingImagineClient(_ExternalImagineClient):
    """Explicit bounded external client that records sanitized fixtures."""

    def __init__(
        self,
        *,
        transport: ImagineTransport,
        policy: ExternalCallPolicy,
        fixture_store: BinaryFixtureStore,
    ) -> None:
        super().__init__(
            mode=ImagineMode.RECORD,
            transport=transport,
            policy=policy,
            fixture_store=fixture_store,
        )


class LiveImagineClient(_ExternalImagineClient):
    """Explicit bounded client that validates outputs without recording metadata."""

    def __init__(
        self,
        *,
        transport: ImagineTransport,
        policy: ExternalCallPolicy,
        asset_store: ContentAddressedAssetStore,
    ) -> None:
        super().__init__(
            mode=ImagineMode.LIVE,
            transport=transport,
            policy=policy,
            asset_store=asset_store,
        )


def build_imagine_client(
    *,
    mode: ImagineMode = ImagineMode.REPLAY,
    fixture_root: Path | str = "fixtures/imagine_signal",
    transport: ImagineTransport | None = None,
    external_policy: ExternalCallPolicy | None = None,
    live_asset_store: ContentAddressedAssetStore | None = None,
) -> ImagineClient:
    """Construct an explicitly configured client, defaulting to offline replay."""

    fixture_store = BinaryFixtureStore(fixture_root)
    if mode == ImagineMode.REPLAY:
        if transport is not None or external_policy is not None or live_asset_store is not None:
            raise ImagineConfigurationError("replay mode cannot receive external-call objects")
        return FixtureImagineClient(fixture_store)
    if transport is None or external_policy is None:
        raise ImagineConfigurationError(
            f"{mode.value} mode requires injected transport and explicit policy"
        )
    if mode == ImagineMode.RECORD:
        if live_asset_store is not None:
            raise ImagineConfigurationError("record mode cannot receive a live asset store")
        return RecordingImagineClient(
            transport=transport,
            policy=external_policy,
            fixture_store=fixture_store,
        )
    if mode == ImagineMode.LIVE:
        if live_asset_store is None:
            raise ImagineConfigurationError("live mode requires an explicit asset store")
        return LiveImagineClient(
            transport=transport,
            policy=external_policy,
            asset_store=live_asset_store,
        )
    raise ImagineConfigurationError(f"unsupported Imagine mode: {mode!r}")


__all__ = [
    "EDIT_SURFACE",
    "GENERATE_SURFACE",
    "FixtureImagineClient",
    "ImagineCallBudgetError",
    "ImagineClientError",
    "ImagineConfigurationError",
    "ImagineResponseError",
    "LiveImagineClient",
    "RecordingImagineClient",
    "build_imagine_client",
]
