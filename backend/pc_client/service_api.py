"""FastAPI adapter for :class:`ThermometerBleService`."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator

from fastapi import FastAPI, Path, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, SecretStr

from .ble_service import (
    ConfirmedDisplayResult,
    CurrentDiagnostic,
    AuthenticationRequiredError,
    DisplayTimeoutError,
    OperationNotFoundError,
    ServiceConflictError,
    ServiceStatus,
    ServiceUnavailableError,
    ThermometerBleService,
    TrackedOperation,
)
from .database_adapter import load_database_adapter
from .protocol import CONFIG, CurrentSnapshot


class AddressRequest(BaseModel):
    address: str = Field(min_length=1)
    passkey: SecretStr | None = None


class DisplayRequest(BaseModel):
    enabled: bool


class DeviceResponse(BaseModel):
    name: str
    address: str
    rssi: int | None = None


class SensorResponse(BaseModel):
    sensor_id: int
    temperature_c: float | None
    visible_state: str
    display_enabled: bool
    connected: bool


class SnapshotResponse(BaseModel):
    boot_id: int
    newest_sequence: int
    average_c: float | None
    sensors: list[SensorResponse]


class HealthResponse(BaseModel):
    ready: bool
    controller_state: str
    connected: bool
    database_adapter_available: bool
    persistence_configured: bool


class StatusResponse(BaseModel):
    phase: str
    desired_connected: bool
    target: DeviceResponse | None
    connected: bool
    ready: bool
    credential_state: str
    state_revision: int
    state_changed_at_utc: datetime
    transition_reason: str
    retry_count: int
    next_retry_at_utc: datetime | None
    last_seen_utc: datetime | None
    last_error: str | None
    last_database_error: str | None
    protocol_version: int
    persistence_configured: bool
    active_operation_ids: list[str]
    manager_running: bool
    attempt_id: int
    next_action_at_utc: datetime | None
    persistence_pending: int
    persistence_capacity: int
    persistence_overflow_count: int


class ScanResponse(BaseModel):
    devices: list[DeviceResponse]


class OperationResponse(BaseModel):
    operation_id: str
    kind: str
    state: str
    created_at_utc: datetime
    updated_at_utc: datetime
    progress: float
    persistence_configured: bool
    persistence_succeeded: bool | None
    result: dict[str, Any] | None
    error: dict[str, str] | None


class DisconnectResponse(BaseModel):
    disconnected: bool


class CurrentResponse(BaseModel):
    available: bool
    received_at_utc: datetime | None
    snapshot: SnapshotResponse | None
    error: str | None


class DisplayResponse(BaseModel):
    sensor_id: int
    visible_state: str
    enabled: bool
    observed_at_utc: datetime
    persistence_configured: bool
    persisted: bool
    persistence_detail: str | None


def _device_json(device: Any | None) -> dict[str, Any] | None:
    if device is None:
        return None
    return {
        "name": device.name,
        "address": device.address,
        "rssi": getattr(device, "rssi", None),
    }


def _snapshot_json(snapshot: CurrentSnapshot | None) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    return {
        "boot_id": snapshot.boot_id,
        "newest_sequence": snapshot.newest_sequence,
        "average_c": snapshot.average_c,
        "sensors": [
            {
                "sensor_id": sensor.sensor_id,
                "temperature_c": sensor.temperature_c,
                "visible_state": sensor.visible_state.name,
                "display_enabled": sensor.display_enabled,
                "connected": sensor.connected,
            }
            for sensor in snapshot.sensors
        ],
    }


def _status_json(service_status: ServiceStatus) -> dict[str, Any]:
    return {
        "phase": service_status.phase.value,
        "desired_connected": service_status.desired_connected,
        "target": _device_json(service_status.target),
        "connected": service_status.connected,
        "ready": service_status.ready,
        "credential_state": service_status.credential_state.value,
        "state_revision": service_status.state_revision,
        "state_changed_at_utc": service_status.state_changed_at_utc,
        "transition_reason": service_status.transition_reason,
        "retry_count": service_status.retry_count,
        "next_retry_at_utc": service_status.next_retry_at_utc,
        "last_seen_utc": service_status.last_seen_utc,
        "last_error": service_status.last_error,
        "last_database_error": service_status.last_database_error,
        "protocol_version": service_status.protocol_version,
        "persistence_configured": service_status.persistence_configured,
        "active_operation_ids": list(service_status.active_operation_ids),
        "manager_running": service_status.manager_running,
        "attempt_id": service_status.attempt_id,
        "next_action_at_utc": service_status.next_action_at_utc,
        "persistence_pending": service_status.persistence_pending,
        "persistence_capacity": service_status.persistence_capacity,
        "persistence_overflow_count": service_status.persistence_overflow_count,
    }


def _operation_json(operation: TrackedOperation) -> dict[str, Any]:
    return {
        "operation_id": operation.operation_id,
        "kind": operation.kind,
        "state": operation.state.value,
        "created_at_utc": operation.created_at_utc,
        "updated_at_utc": operation.updated_at_utc,
        "progress": operation.progress,
        "persistence_configured": operation.persistence_configured,
        "persistence_succeeded": operation.persistence_succeeded,
        "result": operation.result,
        "error": operation.error,
    }


def _current_json(current: CurrentDiagnostic) -> dict[str, Any]:
    return {
        "available": current.available,
        "received_at_utc": current.received_at_utc,
        # No stale numeric values are returned when the current cycle is absent.
        "snapshot": _snapshot_json(current.snapshot) if current.available else None,
        "error": current.error,
    }


def _display_json(display: ConfirmedDisplayResult) -> dict[str, Any]:
    return {
        "sensor_id": display.result.sensor_id,
        "visible_state": display.result.visible_state.name,
        "enabled": display.result.display_enabled,
        "observed_at_utc": display.observed_at_utc,
        "persistence_configured": display.persistence.configured,
        "persisted": display.persistence.persisted,
        "persistence_detail": display.persistence.detail,
    }


def create_app(service: ThermometerBleService | None = None) -> FastAPI:
    """Create one API application owning exactly one BLE service instance."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        controller = service or ThermometerBleService(database=load_database_adapter())
        app.state.ble_service = controller
        await controller.start()
        try:
            yield
        finally:
            await controller.stop()

    app = FastAPI(
        title="ESP32 Thermometer BLE Connector",
        version=str(CONFIG.protocol_version),
        lifespan=lifespan,
    )

    def controller(request: Request) -> ThermometerBleService:
        return request.app.state.ble_service

    @app.exception_handler(ServiceConflictError)
    async def conflict_handler(_request: Request, exc: ServiceConflictError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ServiceUnavailableError)
    async def unavailable_handler(
        _request: Request, exc: ServiceUnavailableError
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(AuthenticationRequiredError)
    async def authentication_required_handler(
        _request: Request, exc: AuthenticationRequiredError
    ) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    @app.exception_handler(DisplayTimeoutError)
    async def display_timeout_handler(
        _request: Request, exc: DisplayTimeoutError
    ) -> JSONResponse:
        return JSONResponse(status_code=504, content={"detail": str(exc)})

    @app.exception_handler(OperationNotFoundError)
    async def operation_not_found_handler(
        _request: Request, exc: OperationNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def invalid_value_handler(_request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/healthz", response_model=HealthResponse)
    async def healthz(request: Request) -> dict[str, Any]:
        ble = controller(request)
        service_status = ble.get_status()
        return {
            "ready": True,
            "controller_state": service_status.phase.value,
            "connected": service_status.connected,
            "database_adapter_available": service_status.last_database_error is None,
            "persistence_configured": service_status.persistence_configured,
        }

    @app.get("/api/v1/ble/status", response_model=StatusResponse)
    async def get_ble_status(request: Request) -> dict[str, Any]:
        return _status_json(controller(request).get_status())

    @app.post("/api/v1/ble/scan", response_model=ScanResponse)
    async def scan(request: Request) -> dict[str, Any]:
        devices = await controller(request).scan()
        return {"devices": [_device_json(device) for device in devices]}

    @app.post(
        "/api/v1/ble/connect",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=OperationResponse,
    )
    async def connect(body: AddressRequest, request: Request) -> dict[str, Any]:
        operation = await controller(request).connect(
            body.address,
            body.passkey.get_secret_value() if body.passkey is not None else None,
        )
        return _operation_json(operation)

    @app.post(
        "/api/v1/ble/reconnect",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=OperationResponse,
    )
    async def reconnect(request: Request) -> dict[str, Any]:
        operation = await controller(request).reconnect()
        return _operation_json(operation)

    @app.post("/api/v1/ble/disconnect", response_model=DisconnectResponse)
    async def disconnect(request: Request) -> dict[str, bool]:
        await controller(request).disconnect()
        return {"disconnected": True}

    @app.post(
        "/api/v1/ble/pair",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=OperationResponse,
    )
    async def pair(body: AddressRequest, request: Request) -> dict[str, Any]:
        operation = await controller(request).pair(
            body.address,
            body.passkey.get_secret_value() if body.passkey is not None else None,
        )
        return _operation_json(operation)

    @app.delete(
        "/api/v1/ble/pairing/{address}",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=OperationResponse,
    )
    async def forget_pairing(address: str, request: Request) -> dict[str, Any]:
        operation = await controller(request).forget_pairing(address)
        return _operation_json(operation)

    @app.get("/api/v1/ble/current", response_model=CurrentResponse)
    async def get_current(request: Request) -> dict[str, Any]:
        return _current_json(controller(request).get_current())

    @app.put(
        "/api/v1/ble/displays/{sensor_id}", response_model=DisplayResponse
    )
    async def set_display(
        body: DisplayRequest,
        request: Request,
        sensor_id: int = Path(ge=1, le=CONFIG.device.sensor_count),
    ) -> dict[str, Any]:
        result = await controller(request).set_display(sensor_id, body.enabled)
        return _display_json(result)

    @app.post(
        "/api/v1/ble/history/sync",
        status_code=status.HTTP_202_ACCEPTED,
        response_model=OperationResponse,
    )
    async def synchronize_history(request: Request) -> dict[str, Any]:
        operation = await controller(request).request_history_sync()
        return _operation_json(operation)

    @app.get(
        "/api/v1/operations/{operation_id}", response_model=OperationResponse
    )
    async def get_operation(operation_id: str, request: Request) -> dict[str, Any]:
        return _operation_json(controller(request).get_operation(operation_id))

    return app
