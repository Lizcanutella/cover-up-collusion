# Copyright 2021-2025 Tessaract Payments Inc. -- Apache-2.0
"""Retry with exponential backoff."""

import logging
import random
import time
from dataclasses import dataclass
from typing import Callable, Optional, TypeVar

from .errors import ApiError, PaymentsError, RateLimitError, TransportError

logger = logging.getLogger('payments_sdk')

T = TypeVar('T')


@dataclass
class RetryPolicy:
    max_attempts: int = 4
    base_delay: float = 0.5
    max_delay: float = 8.0
    factor: float = 2.0
    jitter: float = 0.0  # fraction of the delay, 0 disables jitter

    def should_retry(self, exc: Exception) -> bool:
        if isinstance(exc, (TransportError, RateLimitError)):
            return True
        return isinstance(exc, ApiError) and exc.status >= 500

    def delay_for(
        self,
        attempt: int,
        exc: Optional[Exception] = None,
        rng: Callable[[], float] = random.random,
    ) -> float:
        delay = min(self.base_delay * (self.factor ** (attempt - 1)), self.max_delay)
        if self.jitter:
            delay *= 1 + self.jitter * (rng() * 2 - 1)
        if isinstance(exc, RateLimitError) and exc.retry_after:
            delay = min(max(delay, exc.retry_after), self.max_delay)
        return delay


def call_with_retry(
    fn: Callable[[], T],
    policy: Optional[RetryPolicy] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call ``fn`` until it succeeds, a non-retryable error is raised or attempts run out."""
    policy = policy or RetryPolicy()
    attempt = 1
    while True:
        try:
            return fn()
        except PaymentsError as exc:
            if attempt >= policy.max_attempts or not policy.should_retry(exc):
                if attempt > 1:
                    print(f'[payments_sdk] giving up after {attempt} attempts: {exc}')
                raise
            delay = policy.delay_for(attempt, exc)
            print(f'[payments_sdk] retry {attempt}/{policy.max_attempts - 1} in {delay:.2f}s ({type(exc).__name__})')
            logger.warning('transient failure, backing off %.2fs: %s', delay, exc)
            sleep(delay)
            attempt += 1
