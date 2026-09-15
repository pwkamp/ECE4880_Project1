"""Exclusive resource locks shared by local runner processes."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path
from typing import Iterable, List


class ResourceBusyError(RuntimeError):
    pass


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        # On Windows, signal 0 is CTRL_C_EVENT.  Using the POSIX liveness
        # idiom os.kill(pid, 0) therefore interrupts the runner itself when
        # it inspects a lock owned by the current process.
        import _winapi

        try:
            handle = _winapi.OpenProcess(_winapi.SYNCHRONIZE, False, pid)
        except OSError as error:
            # ERROR_INVALID_PARAMETER means the PID does not exist.  Treat
            # access-denied and other failures conservatively as still alive.
            return getattr(error, "winerror", None) != 87
        try:
            return _winapi.WaitForSingleObject(handle, 0) == _winapi.WAIT_TIMEOUT
        finally:
            _winapi.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _owner_is_alive(path: Path) -> bool:
    try:
        first_line = path.read_text(encoding="utf-8").splitlines()[0]
        pid = int(first_line.removeprefix("pid="))
    except (OSError, ValueError, IndexError):
        return False
    return _pid_is_alive(pid)


class ResourceLockSet:
    def __init__(self, names: Iterable[str]) -> None:
        self.names = sorted(set(names))
        self._paths: List[Path] = []

    def acquire(self) -> None:
        root = Path(tempfile.gettempdir()) / "thermometer-test-locks"
        root.mkdir(parents=True, exist_ok=True)
        try:
            for name in self.names:
                digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]
                path = root / f"{digest}.lock"
                try:
                    descriptor = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                except FileExistsError as error:
                    if not _owner_is_alive(path):
                        try:
                            path.unlink()
                            descriptor = os.open(
                                str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY
                            )
                        except (FileExistsError, FileNotFoundError):
                            raise ResourceBusyError(
                                f"exclusive resource {name!r} changed ownership during reservation"
                            ) from error
                    else:
                        raise ResourceBusyError(
                            f"exclusive resource {name!r} is already reserved"
                        ) from error
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    stream.write(f"pid={os.getpid()}\nresource={name}\n")
                self._paths.append(path)
        except BaseException:
            self.release()
            raise

    def release(self) -> None:
        for path in reversed(self._paths):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        self._paths.clear()

    def __enter__(self) -> "ResourceLockSet":
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()
