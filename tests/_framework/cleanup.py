"""LIFO cleanup stack that preserves every teardown failure."""

from __future__ import annotations

from contextlib import ExitStack
from typing import Callable, List


class CleanupStack:
    def __init__(self) -> None:
        self._stack = ExitStack()
        self.errors: List[str] = []

    def callback(self, callback: Callable[..., object], *args: object, **kwargs: object) -> None:
        self._stack.callback(callback, *args, **kwargs)

    def close(self) -> None:
        try:
            self._stack.close()
        except Exception as error:
            self.errors.append(str(error))
