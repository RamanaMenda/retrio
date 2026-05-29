"""Core retry engine for retrio.

This module exposes `RetryConfig`, `RetryState`, `Retrying`, and `retry`.
Implementation focuses on sync/async parity and emits lifecycle events used by
observability adapters. Helpers for logging and event emission live in
`_observability.py` to keep this module focused on retry semantics.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from functools import wraps
from inspect import isawaitable, iscoroutinefunction
from random import Random
from time import monotonic, sleep
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])
from ._observability import (
    RetryEvent,
    _emit_event,
    _format_event,
    _log_level_for_event,
    _safe_event_callback,
    _safe_state_callback,
)


@dataclass(slots=True)
class RetryState:
    """Immutable snapshot of retry state for hooks and logs."""

    attempt: int
    max_attempts: int
    exception: BaseException | None = None
    result: Any = None
    delay: float = 0.0
    elapsed: float = 0.0
    event: RetryEvent = "attempt_start"


@dataclass(slots=True)
class RetryConfig:
    """Configuration for retry behavior across sync and async paths."""

    max_attempts: int = 3
    initial_delay: float = 0.1
    max_delay: float = 10.0
    multiplier: float = 2.0
    jitter: str = "full"
    retry_exceptions: tuple[type[BaseException], ...] = (Exception,)
    retry_on_result: Callable[[Any], bool] | None = None
    on_retry: Callable[[RetryState], None] | None = None
    on_success: Callable[[RetryState], None] | None = None
    on_failure: Callable[[RetryState], None] | None = None
    on_event: Callable[[RetryEvent, RetryState], None] | None = None
    on_callback_error: Callable[[str, Exception], None] | None = None
    callback_error_mode: str = "ignore"
    logger: Any | None = None
    logger_name: str = "retrio"
    enable_logging: bool = False
    log_style: str = "pretty"
    random: Random = field(default_factory=Random)

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.initial_delay < 0:
            raise ValueError("initial_delay must be >= 0")
        if self.max_delay < 0:
            raise ValueError("max_delay must be >= 0")
        if self.multiplier <= 0:
            raise ValueError("multiplier must be > 0")
        if self.jitter not in {"none", "equal", "full"}:
            raise ValueError("jitter must be one of: none, equal, full")
        if self.callback_error_mode not in {"ignore", "raise"}:
            raise ValueError("callback_error_mode must be one of: ignore, raise")
        if self.log_style not in {"pretty", "structured"}:
            raise ValueError("log_style must be one of: pretty, structured")


class Retrying:
    """Retry executor that supports both direct calls and decorators."""

    def __init__(self, config: RetryConfig | None = None) -> None:
        self.config = config or RetryConfig()

    def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return _sync_retry_call(func, self.config, *args, **kwargs)

    async def acall(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        return await _async_retry_call(func, self.config, *args, **kwargs)

    def wrap(self, func: F) -> F:
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            return self.call(func, *args, **kwargs)

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            return await self.acall(func, *args, **kwargs)

        if iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]


def _compute_delay(config: RetryConfig, attempt: int) -> float:
    delay = min(config.max_delay, config.initial_delay * (config.multiplier ** (attempt - 1)))
    if config.jitter == "none":
        return delay
    if config.jitter == "equal":
        return delay / 2 + config.random.random() * (delay / 2)
    return config.random.random() * delay


def _should_retry(config: RetryConfig, value: Any = None, exc: BaseException | None = None) -> bool:
    if exc is not None:
        return isinstance(exc, config.retry_exceptions)
    if config.retry_on_result is not None:
        return config.retry_on_result(value)
    return False


async def _sleep(delay: float) -> None:
    import asyncio

    await asyncio.sleep(delay)


def _callback_error(config: RetryConfig, callback_name: str, exc: Exception) -> None:
    if config.on_callback_error is not None:
        try:
            config.on_callback_error(callback_name, exc)
        except Exception:
            pass

    if config.enable_logging or config.logger is not None:
        logger = config.logger or logging.getLogger(config.logger_name)
        logger.warning(
            "retrio callback error: callback=%s error=%s",
            callback_name,
            exc,
        )

    if config.callback_error_mode == "raise":
        raise exc


def _safe_state_callback(
    config: RetryConfig,
    callback_name: str,
    callback: Callable[[RetryState], None] | None,
    state: RetryState,
) -> None:
    if callback is None:
        return
    try:
        callback(state)
    except Exception as exc:
        _callback_error(config, callback_name, exc)


def _safe_event_callback(config: RetryConfig, event: RetryEvent, state: RetryState) -> None:
    if config.on_event is None:
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


def _format_event(config: RetryConfig, state: RetryState) -> str:
    exc_name = state.exception.__class__.__name__ if state.exception is not None else "none"
    if config.log_style == "structured":
        return (
            f"event={state.event} attempt={state.attempt}/{state.max_attempts} "
            f"delay={state.delay:.3f}s elapsed={state.elapsed:.3f}s exception={exc_name}"
        )
    return (
        f"retrio {state.event}: attempt {state.attempt}/{state.max_attempts}, "
        f"delay={state.delay:.3f}s, elapsed={state.elapsed:.3f}s, exception={exc_name}"
    )


def _emit_event(config: RetryConfig, event: RetryEvent, state: RetryState) -> RetryState:
    event_state = RetryState(
        attempt=state.attempt,
        max_attempts=state.max_attempts,
        exception=state.exception,
        result=state.result,
        delay=state.delay,
        elapsed=state.elapsed,
        event=event,
    )

    if config.enable_logging or config.logger is not None:
        logger = config.logger or logging.getLogger(config.logger_name)
        logger.log(_log_level_for_event(event), _format_event(config, event_state))

    _safe_event_callback(config, event, event_state)
    return event_state


async def _async_retry_call(func: Callable[..., Any], config: RetryConfig, *args: Any, **kwargs: Any) -> Any:
    start = monotonic()
    last_state = RetryState(attempt=1, max_attempts=config.max_attempts)
    for attempt in range(1, config.max_attempts + 1):
        last_state = _emit_event(
            config,
            "attempt_start",
            RetryState(
                attempt=attempt,
                max_attempts=config.max_attempts,
                elapsed=monotonic() - start,
            ),
        )
        try:
            result = func(*args, **kwargs)
            if isawaitable(result):
                result = await result
            if attempt < config.max_attempts and _should_retry(config, value=result):
                delay = _compute_delay(config, attempt)
                last_state = _emit_event(
                    config,
                    "retry_scheduled",
                    RetryState(
                        attempt=attempt,
                        max_attempts=config.max_attempts,
                        result=result,
                        delay=delay,
                        elapsed=monotonic() - start,
                    ),
                )
                _safe_state_callback(config, "on_retry", config.on_retry, last_state)
                await _sleep(delay)
                continue
            last_state = _emit_event(
                config,
                "attempt_success",
                RetryState(
                    attempt=attempt,
                    max_attempts=config.max_attempts,
                    result=result,
                    elapsed=monotonic() - start,
                ),
            )
            _safe_state_callback(config, "on_success", config.on_success, last_state)
            return result
        except Exception as exc:
            last_state = _emit_event(
                config,
                "attempt_failure",
                RetryState(
                    attempt=attempt,
                    max_attempts=config.max_attempts,
                    exception=exc,
                    elapsed=monotonic() - start,
                ),
            )
            if attempt >= config.max_attempts or not _should_retry(config, exc=exc):
                last_state = _emit_event(
                    config,
                    "retry_exhausted",
                    RetryState(
                        attempt=attempt,
                        max_attempts=config.max_attempts,
                        exception=exc,
                        elapsed=monotonic() - start,
                    ),
                )
                _safe_state_callback(config, "on_failure", config.on_failure, last_state)
                raise
            delay = _compute_delay(config, attempt)
            last_state = _emit_event(
                config,
                "retry_scheduled",
                RetryState(
                    attempt=attempt,
                    max_attempts=config.max_attempts,
                    exception=exc,
                    delay=delay,
                    elapsed=monotonic() - start,
                ),
            )
            _safe_state_callback(config, "on_retry", config.on_retry, last_state)
            await _sleep(delay)
    last_state = _emit_event(config, "retry_exhausted", last_state)
    _safe_state_callback(config, "on_failure", config.on_failure, last_state)
    raise RuntimeError("retry exhausted")


def _sync_retry_call(func: Callable[..., Any], config: RetryConfig, *args: Any, **kwargs: Any) -> Any:
    start = monotonic()
    last_state = RetryState(attempt=1, max_attempts=config.max_attempts)
    for attempt in range(1, config.max_attempts + 1):
        last_state = _emit_event(
            config,
            "attempt_start",
            RetryState(
                attempt=attempt,
                max_attempts=config.max_attempts,
                elapsed=monotonic() - start,
            ),
        )
        try:
            result = func(*args, **kwargs)
            if attempt < config.max_attempts and _should_retry(config, value=result):
                delay = _compute_delay(config, attempt)
                last_state = _emit_event(
                    config,
                    "retry_scheduled",
                    RetryState(
                        attempt=attempt,
                        max_attempts=config.max_attempts,
                        result=result,
                        delay=delay,
                        elapsed=monotonic() - start,
                    ),
                )
                _safe_state_callback(config, "on_retry", config.on_retry, last_state)
                sleep(delay)
                continue
            last_state = _emit_event(
                config,
                "attempt_success",
                RetryState(
                    attempt=attempt,
                    max_attempts=config.max_attempts,
                    result=result,
                    elapsed=monotonic() - start,
                ),
            )
            _safe_state_callback(config, "on_success", config.on_success, last_state)
            return result
        except Exception as exc:
            last_state = _emit_event(
                config,
                "attempt_failure",
                RetryState(
                    attempt=attempt,
                    max_attempts=config.max_attempts,
                    exception=exc,
                    elapsed=monotonic() - start,
                ),
            )
            if attempt >= config.max_attempts or not _should_retry(config, exc=exc):
                last_state = _emit_event(
                    config,
                    "retry_exhausted",
                    RetryState(
                        attempt=attempt,
                        max_attempts=config.max_attempts,
                        exception=exc,
                        elapsed=monotonic() - start,
                    ),
                )
                _safe_state_callback(config, "on_failure", config.on_failure, last_state)
                raise
            delay = _compute_delay(config, attempt)
            last_state = _emit_event(
                config,
                "retry_scheduled",
                RetryState(
                    attempt=attempt,
                    max_attempts=config.max_attempts,
                    exception=exc,
                    delay=delay,
                    elapsed=monotonic() - start,
                ),
            )
            _safe_state_callback(config, "on_retry", config.on_retry, last_state)
            sleep(delay)
    last_state = _emit_event(config, "retry_exhausted", last_state)
    _safe_state_callback(config, "on_failure", config.on_failure, last_state)
    raise RuntimeError("retry exhausted")


def retry(config: RetryConfig | None = None) -> Callable[[F], F]:
    """Decorator factory for retry-enabled sync and async callables."""

    retrying = Retrying(config)

    def decorator(func: F) -> F:
        return retrying.wrap(func)

    return decorator
