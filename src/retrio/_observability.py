from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Literal

RetryEvent = Literal[
    "attempt_start",
    "retry_scheduled",
    "attempt_success",
    "attempt_failure",
    "retry_exhausted",
]


_DEFAULT_LIBRARY_LOGGER = logging.getLogger("retrio")
_DEFAULT_LIBRARY_LOGGER.addHandler(logging.NullHandler())


def _callback_error(config: Any, callback_name: str, exc: Exception) -> None:
    """Handle errors raised by user-provided callbacks according to config.

    This logs the error and optionally re-raises depending on
    `config.callback_error_mode`.
    """
    if getattr(config, "on_callback_error", None) is not None:
        try:
            config.on_callback_error(callback_name, exc)
        except Exception:
            pass

    if getattr(config, "enable_logging", False) or getattr(config, "logger", None) is not None:
        logger = config.logger or logging.getLogger(getattr(config, "logger_name", "retrio"))
        logger.warning(
            "retrio callback error: callback=%s error=%s",
            callback_name,
            exc,
        )

    if getattr(config, "callback_error_mode", "ignore") == "raise":
        raise exc


def _safe_state_callback(
    config: Any,
    callback_name: str,
    callback: Callable[[Any], None] | None,
    state: Any,
) -> None:
    """Invoke a state callback and handle exceptions safely."""
    if callback is None:
        return
    try:
        callback(state)
    except Exception as exc:
        _callback_error(config, callback_name, exc)


def _safe_event_callback(config: Any, event: RetryEvent, state: Any) -> None:
    """Invoke the generic event callback with safety wrapper."""
    if getattr(config, "on_event", None) is None:
        return
    try:
        config.on_event(event, state)
    except Exception as exc:
        _callback_error(config, "on_event", exc)


def _log_level_for_event(event: RetryEvent) -> int:
    if event == "attempt_start":
        return logging.DEBUG
    if event == "retry_scheduled":
        return logging.INFO
    if event == "attempt_success":
        return logging.INFO
    if event == "attempt_failure":
        return logging.WARNING
    return logging.ERROR


def _format_event(config: Any, state: Any) -> str:
    exc_name = state.exception.__class__.__name__ if state.exception is not None else "none"
    if getattr(config, "log_style", "pretty") == "structured":
        return (
            f"event={state.event} attempt={state.attempt}/{state.max_attempts} "
            f"delay={state.delay:.3f}s elapsed={state.elapsed:.3f}s exception={exc_name}"
        )
    return (
        f"retrio {state.event}: attempt {state.attempt}/{state.max_attempts}, "
        f"delay={state.delay:.3f}s, elapsed={state.elapsed:.3f}s, exception={exc_name}"
    )


def _emit_event(config: Any, event: RetryEvent, state: Any) -> Any:
    """Emit an event: log it and call the generic event callback.

    Returns an event-annotated snapshot of state suitable for passing to
    user callbacks.
    """
    event_state = type(state)(
        attempt=state.attempt,
        max_attempts=state.max_attempts,
        exception=state.exception,
        result=getattr(state, "result", None),
        delay=state.delay,
        elapsed=getattr(state, "elapsed", 0.0),
        event=event,
    )

    if getattr(config, "enable_logging", False) or getattr(config, "logger", None) is not None:
        logger = config.logger or logging.getLogger(getattr(config, "logger_name", "retrio"))
        logger.log(_log_level_for_event(event), _format_event(config, event_state))

    _safe_event_callback(config, event, event_state)
    return event_state
