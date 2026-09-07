from datetime import datetime, timezone
import unittest
import warnings

warnings.filterwarnings("ignore", message="Using `httpx` with `starlette.testclient`.*")
from fastapi.testclient import TestClient

from pc_client.ble_service import (
    ConfirmedDisplayResult,
    AuthenticationRequiredError,
    ConnectionPhase,
    CredentialState,
    CurrentDiagnostic,
    DisplayTimeoutError,
    OperationNotFoundError,
    OperationState,
    ServiceConflictError,
    ServiceStatus,
    ServiceUnavailableError,
    TrackedOperation,
)
from pc_client.database_adapter import DeviceIdentity, PersistenceResult
from pc_client.protocol import (
    CONFIG,
    CurrentSnapshot,
    DisplayResult,
    SensorSnapshot,
    VisibleState,
)
from pc_client.service_api import create_app
from pc_client.thermometer_client import DiscoveredThermometer


NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
ADDRESS = "AA:BB:CC:DD:EE:FF"
DEVICE_NAME = "Thermometer-Test-01"


def operation(kind="connect") -> TrackedOperation:
    return TrackedOperation(
        "operation-1",
        kind,
        OperationState.RUNNING,
        NOW,
        NOW,
        persistence_configured=False,
    )


def current_snapshot() -> CurrentSnapshot:
    return CurrentSnapshot(
        10,
        20,
        (
            SensorSnapshot(1, 20.5, VisibleState.ON, True),
            SensorSnapshot(2, None, VisibleState.DISCONNECTED, False),
        ),
        None,
    )


class StubService:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.scan_error = None
        self.display_error = None
        self.last_connect_address = None
        self.last_connect_passkey = None
        self.last_pair_address = None
        self.last_forgotten_address = None
        self.connect_error = None

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    def get_status(self):
        return ServiceStatus(
            phase=ConnectionPhase.CONNECTED,
            desired_connected=True,
            target=DeviceIdentity(ADDRESS, DEVICE_NAME),
            connected=True,
            ready=True,
            credential_state=CredentialState.VERIFIED,
            state_revision=8,
            state_changed_at_utc=NOW,
            transition_reason="protected protocol verified",
            retry_count=0,
            next_retry_at_utc=None,
            last_seen_utc=NOW,
            last_error=None,
            last_database_error=None,
            protocol_version=CONFIG.protocol_version,
            persistence_configured=False,
            active_operation_ids=("operation-1",),
        )

    async def scan(self):
        if self.scan_error:
            raise self.scan_error
        return [DiscoveredThermometer(DEVICE_NAME, ADDRESS, object(), -42)]

    async def connect(self, address, passkey=None):
        if self.connect_error:
            raise self.connect_error
        self.last_connect_address = address
        self.last_connect_passkey = passkey
        return operation()

    async def reconnect(self):
        return operation("reconnect")

    async def disconnect(self):
        pass

    async def pair(self, address, passkey=None):
        self.last_pair_address = address
        return operation("pair")

    async def forget_pairing(self, address):
        self.last_forgotten_address = address
        return operation("forget_pairing")

    def get_current(self):
        return CurrentDiagnostic(True, NOW, current_snapshot())

    async def set_display(self, sensor_id, enabled):
        if self.display_error:
            raise self.display_error
        return ConfirmedDisplayResult(
            DisplayResult(sensor_id, VisibleState.ON, enabled),
            NOW,
            PersistenceResult(False, False, "not configured"),
        )

    async def request_history_sync(self):
        return operation("history_sync:manual")

    def get_operation(self, operation_id):
        if operation_id != "operation-1":
            raise OperationNotFoundError("operation was not found")
        return operation()


class ServiceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = StubService()
        self.client_context = TestClient(create_app(self.service))
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)

    def test_lifecycle_and_read_endpoints(self):
        self.assertTrue(self.service.started)
        health = self.client.get("/healthz")
        status = self.client.get("/api/v1/ble/status")
        current = self.client.get("/api/v1/ble/current")

        self.assertEqual(health.status_code, 200)
        self.assertTrue(health.json()["ready"])
        self.assertEqual(status.json()["target"]["address"], ADDRESS)
        self.assertEqual(current.json()["snapshot"]["sensors"][0]["temperature_c"], 20.5)

    def test_all_control_endpoints_return_their_contracts(self):
        scan = self.client.post("/api/v1/ble/scan")
        connect = self.client.post(
            "/api/v1/ble/connect",
            json={"address": ADDRESS, "passkey": "012345"},
        )
        reconnect = self.client.post("/api/v1/ble/reconnect")
        pair = self.client.post("/api/v1/ble/pair", json={"address": ADDRESS})
        forget = self.client.delete(f"/api/v1/ble/pairing/{ADDRESS}")
        display = self.client.put("/api/v1/ble/displays/1", json={"enabled": True})
        history = self.client.post("/api/v1/ble/history/sync")
        get_operation = self.client.get("/api/v1/operations/operation-1")
        disconnect = self.client.post("/api/v1/ble/disconnect")

        self.assertEqual(scan.json()["devices"][0]["rssi"], -42)
        for response in (connect, reconnect, pair, forget, history):
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json()["operation_id"], "operation-1")
        self.assertTrue(display.json()["enabled"])
        self.assertEqual(get_operation.status_code, 200)
        self.assertEqual(disconnect.json(), {"disconnected": True})
        self.assertEqual(self.service.last_connect_address, ADDRESS)
        self.assertEqual(self.service.last_connect_passkey, "012345")
        self.assertNotIn("012345", connect.text)

    def test_validation_and_service_errors_are_mapped(self):
        invalid_address = self.client.post("/api/v1/ble/connect", json={"address": ""})
        invalid_sensor = self.client.put("/api/v1/ble/displays/3", json={"enabled": True})
        self.service.scan_error = ServiceConflictError("connected")
        conflict = self.client.post("/api/v1/ble/scan")
        self.service.display_error = DisplayTimeoutError("too slow")
        timeout = self.client.put("/api/v1/ble/displays/1", json={"enabled": True})
        missing = self.client.get("/api/v1/operations/does-not-exist")

        self.assertEqual(invalid_address.status_code, 422)
        self.assertEqual(invalid_sensor.status_code, 422)
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(timeout.status_code, 504)
        self.assertEqual(missing.status_code, 404)

    def test_unavailable_maps_to_503(self):
        self.service.display_error = ServiceUnavailableError("offline")
        response = self.client.put("/api/v1/ble/displays/1", json={"enabled": True})
        self.assertEqual(response.status_code, 503)

    def test_authentication_required_maps_to_401(self):
        self.service.connect_error = AuthenticationRequiredError("PIN required")
        response = self.client.post(
            "/api/v1/ble/connect", json={"address": ADDRESS}
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "PIN required")


if __name__ == "__main__":
    unittest.main()
