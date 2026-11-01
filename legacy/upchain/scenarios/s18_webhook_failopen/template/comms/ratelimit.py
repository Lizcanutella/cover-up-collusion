"""Per-recipient SMS rate limiting: a token bucket per phone number, so a retry storm or a stuck job can't
flood one person's phone (INC-2025-019)."""

import time
from typing import Callable


class RateLimited(Exception):
    def __init__(self, retry_after: float):
        super().__init__(f"rate limited; retry after {retry_after:.0f}s")
        self.retry_after = retry_after


class TokenBucket:
    def __init__(self, per_minute: int, clock: Callable[[], float] = time.monotonic, burst: int | None = None):
        self.rate = per_minute / 60.0
        self.capacity = burst if burst is not None else max(per_minute // 6, 1)
        self.clock = clock
        self._buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, last refill)

    def take(self, key: str) -> None:
        now = self.clock()
        tokens, last = self._buckets.get(key, (float(self.capacity), now))
        tokens = min(self.capacity, tokens + (now - last) * self.rate)
        if tokens < 1:
            self._buckets[key] = (tokens, now)
            raise RateLimited((1 - tokens) / self.rate)
        self._buckets[key] = (tokens - 1, now)
