"""Prometheus adapter utilities for Retrio.

This adapter is optional and will work with a user-provided metrics client
or with `prometheus_client` if installed. The module avoids importing
prometheus_client at import time to keep Retrio dependency-free.
"""
from __future__ import annotations

from typing import Any


class PrometheusAdapter:
    """Adapter that exposes counters and histograms for retrio events.

    You may pass existing Counter/Histogram objects or let the adapter
    create them when `prometheus_client` is available.
    """

    def __init__(
        self,
        attempts_counter: Any | None = None,
        retries_counter: Any | None = None,
        failures_counter: Any | None = None,
        exhausted_counter: Any | None = None,
        delay_histogram: Any | None = None,
        registry: Any | None = None,
        prefix: str = "retrio",
    ) -> None:
        self.attempts = attempts_counter
        self.retries = retries_counter
        self.failures = failures_counter
        self.exhausted = exhausted_counter
        self.delay_histogram = delay_histogram
        self.prefix = prefix

        # lazy create instruments when prom client available
        if any(x is None for x in (self.attempts, self.retries, self.failures, self.exhausted)):
            try:
                from prometheus_client import Counter, Histogram

                self.attempts = self.attempts or Counter(f"{prefix}_attempts_total", "Attempts")
                self.retries = self.retries or Counter(f"{prefix}_retries_total", "Retries")
                self.failures = self.failures or Counter(f"{prefix}_failures_total", "Failures")
                self.exhausted = self.exhausted or Counter(f"{prefix}_exhausted_total", "Exhausted")
                self.delay_histogram = self.delay_histogram or Histogram(f"{prefix}_delay_seconds", "Backoff delay seconds")
            except Exception:
                # prometheus_client not available; keep user-provided instruments only
                pass

    def on_event(self, event: str, state: Any) -> None:
        if event == "attempt_start":
            if self.attempts is not None:
                try:
                    self.attempts.inc()
                except Exception:
                    pass
        if event == "retry_scheduled":
            if self.retries is not None:
                try:
                    self.retries.inc()
                except Exception:
                    pass
            if self.delay_histogram is not None and getattr(state, "delay", None) is not None:
                try:
                    self.delay_histogram.observe(state.delay)
                except Exception:
                    pass
        if event == "attempt_failure":
            if self.failures is not None:
                try:
                    self.failures.inc()
                except Exception:
                    pass
        if event == "retry_exhausted":
            if self.exhausted is not None:
                try:
                    self.exhausted.inc()
                except Exception:
                    pass
