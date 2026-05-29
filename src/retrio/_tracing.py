"""OpenTelemetry adapter for Retrio lifecycle events.

This module provides a lightweight adapter that maps retrio lifecycle events
to OpenTelemetry spans. It does not require OpenTelemetry to be installed;
users can pass a tracer-like object (duck-typed) to the adapter.
"""
from __future__ import annotations

from typing import Any
import threading


class OpenTelemetryAdapter:
    """Adapter that converts retrio events to OpenTelemetry spans.

    Usage:
        adapter = OpenTelemetryAdapter(tracer)
        config.on_event = adapter.on_event
    """

    def __init__(self, tracer: Any, span_name: str = "retrio.attempt") -> None:
        self.tracer = tracer
        self.span_name = span_name
        # store active span/context per thread+attempt
        self._active: dict[tuple[int, int], Any] = {}

    def _key(self, state: Any) -> tuple[int, int]:
        return (threading.get_ident(), int(state.attempt))

    def on_event(self, event: str, state: Any) -> None:
        key = self._key(state)
        # start span on attempt_start
        if event == "attempt_start":
            # Try to use start_as_current_span if available
            try:
                ctx = self.tracer.start_as_current_span(self.span_name, attributes={
                    "retrio.attempt": state.attempt,
                    "retrio.max_attempts": state.max_attempts,
                })
            except Exception:
                # Fallback: tracer may expose start_span returning a span-like object
                try:
                    span = self.tracer.start_span(self.span_name)
                    self._active[key] = span
                    return
                except Exception:
                    return

            # enter context (sync); store context manager so we can exit later
            try:
                span = ctx.__enter__()
            except AttributeError:
                # ctx is a span-like object
                span = ctx
                self._active[key] = (None, span)
            else:
                self._active[key] = (ctx, span)

        # end span on success/failure/exhausted
        if event in {"attempt_success", "attempt_failure", "retry_exhausted"}:
            stored = self._active.pop(key, None)
            if stored is None:
                return
            if isinstance(stored, tuple):
                ctx, span = stored
                # set status attributes if span available
                try:
                    if hasattr(span, "set_attribute"):
                        span.set_attribute("retrio.event", event)
                except Exception:
                    pass
                # exit context if possible
                try:
                    if ctx is not None:
                        ctx.__exit__(None, None, None)
                    elif hasattr(span, "end"):
                        span.end()
                except Exception:
                    pass
