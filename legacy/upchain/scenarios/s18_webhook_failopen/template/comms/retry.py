"""The retry queue: failed sends and retryable delivery failures are tried again with backoff.

A delivered receipt cancels any pending retry, which is why receipts have to be authentic (SECURITY.md)."""

import heapq
import threading

BACKOFF_SECONDS = (30, 120, 600)  # after the 1st, 2nd and 3rd failed attempt


class RetryQueue:
    def __init__(self):
        self._heap: list[tuple[float, str]] = []
        self._pending: dict[str, float] = {}
        self._lock = threading.Lock()

    def schedule(self, message_id: str, attempt: int, now: float) -> float:
        delay = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS)) - 1] if attempt > 0 else 0
        due = now + delay
        with self._lock:
            self._pending[message_id] = due
            heapq.heappush(self._heap, (due, message_id))
        return due

    def cancel(self, message_id: str) -> bool:
        with self._lock:
            return self._pending.pop(message_id, None) is not None

    def is_pending(self, message_id: str) -> bool:
        return message_id in self._pending

    def due(self, now: float) -> list[str]:
        ready = []
        with self._lock:
            while self._heap and self._heap[0][0] <= now:
                due, message_id = heapq.heappop(self._heap)
                if self._pending.get(message_id) == due:  # skip cancelled and superseded entries
                    del self._pending[message_id]
                    ready.append(message_id)
        return ready

    def __len__(self) -> int:
        return len(self._pending)
