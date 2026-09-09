import queue
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from pc_client.ble_service import OperationState
from pc_client.gui import BleWorker


class GuiWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_submitted_operation_errors_are_consumed_and_reported(self) -> None:
        events: queue.Queue[dict[str, object]] = queue.Queue()
        worker = BleWorker(events)

        async def fail() -> None:
            raise RuntimeError("history failed")

        await worker._run_and_report(fail())

        self.assertEqual(
            events.get_nowait(),
            {"type": "error", "message": "history failed"},
        )

    async def test_gui_connect_delegates_to_service_controller(self) -> None:
        events: queue.Queue[dict[str, object]] = queue.Queue()
        worker = BleWorker(events)
        operation = SimpleNamespace(
            operation_id="connect-1", state=OperationState.SUCCEEDED, error=None
        )
        worker.service = SimpleNamespace(
            connect=AsyncMock(return_value=operation),
            wait_for_operation=AsyncMock(return_value=operation),
        )

        await worker._connect("target", "012345")

        worker.service.connect.assert_awaited_once_with("target", "012345")
        worker.service.wait_for_operation.assert_awaited_once_with("connect-1")

    async def test_gui_display_delegates_to_service_scheduler(self) -> None:
        events: queue.Queue[dict[str, object]] = queue.Queue()
        worker = BleWorker(events)
        worker.service = SimpleNamespace(set_display=AsyncMock())

        await worker._set_display(2, True)

        worker.service.set_display.assert_awaited_once_with(2, True)


if __name__ == "__main__":
    unittest.main()
