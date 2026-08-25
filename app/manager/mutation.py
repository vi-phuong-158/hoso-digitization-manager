from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator


class MutationBusy(RuntimeError):
    """Raised when another long-running metadata mutation owns the lock."""


class MutationLock:
    """Small process-local non-blocking lock for critical manager mutations."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    @contextmanager
    def acquire(self) -> Iterator[None]:
        if not self._lock.acquire(blocking=False):
            raise MutationBusy("Một thao tác dữ liệu khác đang chạy. Vui lòng thử lại sau.")
        try:
            yield
        finally:
            self._lock.release()
