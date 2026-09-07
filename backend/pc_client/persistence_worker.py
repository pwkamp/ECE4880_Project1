"""Bounded, ordered database work that never shifts BLE poll deadlines."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from .database_adapter import PersistenceResult


@dataclass(frozen=True)
class PersistenceHealth:
    pending: int
    capacity: int
    overflow_count: int


@dataclass
class _PersistenceRequest:
    method_name: str
    value: Any
    future: asyncio.Future[PersistenceResult]


class PersistenceWorker:
    """Serialize adapter calls behind a bounded queue."""

    def __init__(
        self,
        execute: Callable[[str, Any], Awaitable[PersistenceResult]],
        *,
        configured: Callable[[], bool],
        capacity: int,
    ) -> None:
        if capacity <= 0:
            raise ValueError("persistence queue capacity must be positive")
        self._execute = execute
        self._configured = configured
        self._queue: asyncio.Queue[_PersistenceRequest] = asyncio.Queue(capacity)
        self._capacity = capacity
        self._overflow_count = 0
        self._task: asyncio.Task[None] | None = None

    @property
    def health(self) -> PersistenceHealth:
        return PersistenceHealth(
            self._queue.qsize(), self._capacity, self._overflow_count
        )

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(
                self._run(), name="thermometer-persistence"
            )

    async def stop(self, *, flush_timeout: float = 1.0) -> None:
        if self._task is None:
            return
        try:
            await asyncio.wait_for(self._queue.join(), timeout=flush_timeout)
        except asyncio.TimeoutError:
            pass
        self._task.cancel()
        await asyncio.gather(self._task, return_exceptions=True)
        self._task = None
        self._fail_pending("service stopped before persistence completed")

    def enqueue(self, method_name: str, value: Any) -> asyncio.Future[PersistenceResult]:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[PersistenceResult] = loop.create_future()
        request = _PersistenceRequest(method_name, value, future)
        try:
            self._queue.put_nowait(request)
        except asyncio.QueueFull:
            self._overflow_count += 1
            future.set_result(
                PersistenceResult(
                    self._configured(),
                    False,
                    "persistence queue is full; this record was not queued",
                )
            )
        return future

    async def submit(self, method_name: str, value: Any) -> PersistenceResult:
        return await self.enqueue(method_name, value)

    async def _run(self) -> None:
        while True:
            request = await self._queue.get()
            try:
                result = await self._execute(request.method_name, request.value)
                if not request.future.done():
                    request.future.set_result(result)
            except asyncio.CancelledError:
                if not request.future.done():
                    request.future.set_result(
                        PersistenceResult(
                            self._configured(), False, "persistence worker stopped"
                        )
                    )
                raise
            except Exception as exc:
                # Adapter defects are isolated to one record. The worker must
                # stay alive so later one-second slots are still attempted.
                if not request.future.done():
                    request.future.set_result(
                        PersistenceResult(
                            self._configured(),
                            False,
                            f"persistence adapter raised {type(exc).__name__}: {exc}",
                        )
                    )
            finally:
                self._queue.task_done()

    def _fail_pending(self, detail: str) -> None:
        while True:
            try:
                request = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            if not request.future.done():
                request.future.set_result(
                    PersistenceResult(self._configured(), False, detail)
                )
            self._queue.task_done()
