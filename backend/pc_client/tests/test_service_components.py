import asyncio
from datetime import datetime, timezone
import unittest

from pc_client.ble_scheduler import BleRequestScheduler, RequestPriority
from pc_client.database_adapter import PersistenceResult
from pc_client.persistence_worker import PersistenceWorker
from pc_client.service_state import (
    ConnectionPhase,
    ControllerState,
    CredentialState,
    transition_state,
)


def initial_state() -> ControllerState:
    return ControllerState(
        phase=ConnectionPhase.DISCONNECTED,
        desired_connected=False,
        target=None,
        connected=False,
        ready=False,
        credential_state=CredentialState.MISSING,
        retry_count=0,
        next_retry_at_utc=None,
        last_seen_utc=None,
        last_error=None,
        revision=0,
        changed_at_utc=datetime.now(timezone.utc),
        reason="test",
    )


class StateReducerTests(unittest.TestCase):
    def test_rejects_ready_state_without_transport(self) -> None:
        with self.assertRaisesRegex(ValueError, "ready BLE service"):
            transition_state(
                initial_state(),
                datetime.now(timezone.utc),
                ready=True,
                connected=False,
                reason="invalid",
            )

    def test_connected_state_is_complete_and_revisioned(self) -> None:
        state = transition_state(
            initial_state(),
            datetime.now(timezone.utc),
            phase=ConnectionPhase.CONNECTED,
            desired_connected=True,
            connected=True,
            ready=True,
            credential_state=CredentialState.VERIFIED,
            reason="verified",
        )
        self.assertEqual(state.revision, 1)
        self.assertTrue(state.connected)
        self.assertTrue(state.ready)


class SchedulerTests(unittest.IsolatedAsyncioTestCase):
    async def test_display_preempts_queued_history(self) -> None:
        ready = True
        scheduler = BleRequestScheduler(lambda: ready)
        scheduler.start()
        first_started = asyncio.Event()
        release_first = asyncio.Event()
        calls: list[str] = []

        async def current() -> str:
            calls.append("current")
            first_started.set()
            await release_first.wait()
            return "current"

        async def action(name: str) -> str:
            calls.append(name)
            return name

        first = asyncio.create_task(
            scheduler.submit(RequestPriority.CURRENT, "current", current)
        )
        await first_started.wait()
        history = asyncio.create_task(
            scheduler.submit(
                RequestPriority.HISTORY,
                "history",
                lambda: action("history"),
            )
        )
        display = asyncio.create_task(
            scheduler.submit(
                RequestPriority.DISPLAY,
                "display",
                lambda: action("display"),
            )
        )
        await asyncio.sleep(0)
        release_first.set()
        self.assertEqual(
            await asyncio.gather(first, history, display),
            ["current", "history", "display"],
        )
        self.assertEqual(calls, ["current", "display", "history"])
        await scheduler.stop(RuntimeError("test complete"))


class PersistenceWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_queue_reports_loss_without_blocking(self) -> None:
        async def execute(_method: str, _value: object) -> PersistenceResult:
            return PersistenceResult(True, True)

        worker = PersistenceWorker(
            execute, configured=lambda: True, capacity=1
        )
        accepted = worker.enqueue("sample", 1)
        rejected = worker.enqueue("sample", 2)

        overflow = await rejected
        self.assertFalse(overflow.persisted)
        self.assertIn("queue is full", overflow.detail or "")
        self.assertEqual(worker.health.overflow_count, 1)

        worker.start()
        self.assertTrue((await accepted).persisted)
        await worker.stop()

    async def test_adapter_exception_does_not_stop_worker(self) -> None:
        calls = 0

        async def execute(_method: str, _value: object) -> PersistenceResult:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ValueError("broken row")
            return PersistenceResult(True, True)

        worker = PersistenceWorker(
            execute, configured=lambda: True, capacity=2
        )
        worker.start()
        failed = await worker.submit("sample", 1)
        succeeded = await worker.submit("sample", 2)

        self.assertFalse(failed.persisted)
        self.assertIn("ValueError", failed.detail or "")
        self.assertTrue(succeeded.persisted)
        await worker.stop()
