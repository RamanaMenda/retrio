"""Token-bucket rate limiter for Retrio.

Provides a simple, thread-safe token bucket implementation.
"""
from __future__ import annotations

from time import monotonic
import threading


class RateLimitExceeded(RuntimeError):
    pass


class TokenBucket:
    """Token bucket limiter.

    - `capacity`: max tokens
    - `refill_rate`: tokens per second
    """

    def __init__(self, capacity: float = 10.0, refill_rate: float = 1.0) -> None:
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self._tokens = float(capacity)
        self._last = monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = monotonic()
        delta = now - self._last
        if delta <= 0:
            return
        self._tokens = min(self.capacity, self._tokens + delta * self.refill_rate)
        self._last = now

    def allow(self, tokens: float = 1.0) -> bool:
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False
