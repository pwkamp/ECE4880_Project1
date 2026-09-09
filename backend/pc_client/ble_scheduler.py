"""Priority-ordered serialization for requester-driven GATT operations."""

from __future__ import annotations

import asyncio
import itertools
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Awaitable, Callable


class RequestPriority(IntEnum):
    # Requirement support: prioritize the <1 s remote display path from
    # SYS-HLR-510 (SCRUM-415) without starving the one-hertz current schedule.
    DISPLAY = 0
    CURRENT = 10
    HISTORY = 20


@dataclass(order=True)
class _ScheduledRequest:
    priority: int
    sequence: int
    name: str = field(compare=False)
    action: Callable[[], Awaitable[Any]] = field(compare=False)
    future: asyncio.Future[Any] = field(compare=False)


class BleRequestScheduler:
    """Run exactly one GATT request at a time, ordered by requirement priority."""

    def __init__(self, ready: Callable[[], bool]) -> None:
        self._ready = ready
        self._queue: asyncio.PriorityQueue[_ScheduledRequest] = (
            asyncio.PriorityQueue()
        )
        self._sequence = itertools.count()
        self._worker: asyncio.Task[None] | None = None

    @property
    def pending_count(self) -> int:
        return self._queue.qsize()

    def start(self) -> None:
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(
                self._run(), name="thermometer-ble-scheduler"
            )

    async def stop(self, error: Exception) -> None:
        if self._worker is not None:
            self._worker.cancel()
            await asyncio.gather(self._worker, return_exceptions=True)
            self._worker = None
        self.fail_pending(error)

    async def submit(
        self,
        priority: RequestPriority,
        name: str,
        action: Callable[[], Awaitable[Any]],
    ) -> Any:
        if not self._ready():
            raise RuntimeError("thermometer is not connected")
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        await self._queue.put(
            _ScheduledRequest(
                int(priority), next(self._sequence), name, action, future
            )
        )
        return await future

    def fail_pending(self, error: Exception) -> None:
        while True:
            try:
                request = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            if not request.future.done():
                request.future.set_exception(error)
            self._queue.task_done()

    async def _run(self) -> None:
        while True:
            request = await self._queue.get()
            try:
                if request.future.cancelled():
                    continue
                if not self._ready():
                    raise RuntimeError("thermometer is not connected")
                result = await request.action()
                if not request.future.done():
                    request.future.set_result(result)
            except asyncio.CancelledError:
                if not request.future.done():
                    request.future.cancel()
                raise
            except Exception as exc:
                if not request.future.done():
                    request.future.set_exception(exc)
            finally:
                self._queue.task_done()
