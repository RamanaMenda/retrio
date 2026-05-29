"""Datadog adapters for tracing and metrics.

This adapter is optional and works with user-supplied `ddtrace` tracer and
`dogstatsd`/`statsd`-like clients. It avoids importing Datadog libraries at
import time so Retrio remains dependency-free.
"""
from __future__ import annotations

from typing import Any


class DatadogAdapter:
    """Adapter that reports retry lifecycle events to Datadog tracer and statsd.

    Usage:
        adapter = DatadogAdapter(tracer=dd_tracer, statsd=dogstatsd)
        config.on_event = adapter.on_event
    """

    def __init__(self, tracer: Any | None = None, statsd: Any | None = None, prefix: str = "retrio") -> None:
        self.tracer = tracer
        self.statsd = statsd
        self.prefix = prefix
        # counters names
        self._attempts = f"{prefix}.attempts"
        self._retries = f"{prefix}.retries"
        self._failures = f"{prefix}.failures"
        self._exhausted = f"{prefix}.exhausted"

    def on_event(self, event: str, state: Any) -> None:
        # metrics
        try:
            if event == "attempt_start" and self.statsd is not None:
                try:
                    self.statsd.increment(self._attempts)
                except Exception:
                    pass
            if event == "retry_scheduled" and self.statsd is not None:
                try:
                    self.statsd.increment(self._retries)
                    if getattr(state, "delay", None) is not None and hasattr(self.statsd, "timing"):
                        try:
                            # dogstatsd.timing expects milliseconds
                            self.statsd.timing(f"{self.prefix}.delay_ms", int(state.delay * 1000))
                        except Exception:
                            pass
                except Exception:
                    pass
            if event == "attempt_failure" and self.statsd is not None:
                try:
                    self.statsd.increment(self._failures)
                except Exception:
                    pass
            if event == "retry_exhausted" and self.statsd is not None:
                try:
                    self.statsd.increment(self._exhausted)
                except Exception:
                    pass
        except Exception:
            # metrics are best-effort
            pass

        # tracing
        if self.tracer is None:
            return
        try:
            # prefer `trace` API (ddtrace)
            if event == "attempt_start":
                try:
                    span = self.tracer.trace("retrio.attempt")
                except Exception:
                    try:
                        span = self.tracer.start_span("retrio.attempt")
                    except Exception:
                        span = None
                if span is not None:
                    # attach some tags
                    try:
                        span.set_tag("retrio.attempt", getattr(state, "attempt", None))
                        span.set_tag("retrio.max_attempts", getattr(state, "max_attempts", None))
                    except Exception:
                        pass
                    # store on the state if possible for end callsites
                    try:
                        setattr(state, "_retrio_datadog_span", span)
                    except Exception:
                        pass
            if event in {"attempt_success", "attempt_failure", "retry_exhausted"}:
                span = getattr(state, "_retrio_datadog_span", None)
                if span is None:
                    return
                try:
                    span.set_tag("retrio.event", event)
                    if getattr(state, "result", None) is not None:
                        span.set_tag("retrio.result_type", type(state.result).__name__)
                    if getattr(state, "exception", None) is not None:
                        span.set_tag("retrio.exception_type", type(state.exception).__name__)
                except Exception:
                    pass
                try:
                    # ddtrace span provides finish()
                    if hasattr(span, "finish"):
                        span.finish()
                    elif hasattr(span, "close"):
                        span.close()
                except Exception:
                    pass
        except Exception:
            # tracing failures should not break user code
            pass
