"""Simple circuit breaker implementation for Retrio.

Provides a thread-safe circuit breaker with closed/open/half-open states.
"""
from __future__ import annotations

import threading
from time import monotonic
# typing.Any was unused


class CircuitOpenError(RuntimeError):
    pass


class CircuitBreaker:
    """A simple circuit breaker.

    - `failure_threshold`: consecutive failures to open the circuit
    - `recovery_timeout`: seconds to wait before transitioning to half-open
    - `half_open_successes`: number of successes in half-open to close
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0, half_open_successes: int = 1) -> None:
        self.failure_threshold = int(failure_threshold)
        self.recovery_timeout = float(recovery_timeout)
        self.half_open_successes = int(half_open_successes)

        self._lock = threading.Lock()
        self._state: str = "closed"
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._half_open_success_count = 0

    def is_open(self) -> bool:
        with self._lock:
            if self._state == "open":
                # check if timeout elapsed
                if monotonic() - self._last_failure_time >= self.recovery_timeout:
                    self._state = "half-open"
                    self._half_open_success_count = 0
                    return False
                return True
            return False

    def allow(self) -> bool:
        return not self.is_open()

    def record_success(self) -> None:
        with self._lock:
            if self._state == "half-open":
                self._half_open_success_count += 1
                if self._half_open_success_count >= self.half_open_successes:
                    # close the circuit
                    self._state = "closed"
                    self._failure_count = 0
                    self._half_open_success_count = 0
            else:
                self._failure_count = 0

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = monotonic()
            if self._failure_count >= self.failure_threshold:
                self._state = "open"
