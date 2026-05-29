from __future__ import annotations

from dataclasses import dataclass, field
from functools import wraps
from inspect import isawaitable, iscoroutinefunction
from random import Random
from time import sleep
from typing import Any, Callable, Iterable, Optional, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


@dataclass(slots=True)
class RetryState:
    attempt: int
    max_attempts: int
    exception: BaseException | None = None
    result: Any = None
    delay: float = 0.0


@dataclass(slots=True)
class RetryConfig:
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
    random: Random = field(default_factory=Random)


class Retrying:
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


async def _async_retry_call(func: Callable[..., Any], config: RetryConfig, *args: Any, **kwargs: Any) -> Any:
    last_state = RetryState(attempt=1, max_attempts=config.max_attempts)
    for attempt in range(1, config.max_attempts + 1):
        try:
            result = func(*args, **kwargs)
            if isawaitable(result):
                result = await result
            if attempt < config.max_attempts and _should_retry(config, value=result):
                delay = _compute_delay(config, attempt)
                last_state = RetryState(attempt=attempt, max_attempts=config.max_attempts, result=result, delay=delay)
                if config.on_retry is not None:
                    config.on_retry(last_state)
                await _sleep(delay)
                continue
            last_state = RetryState(attempt=attempt, max_attempts=config.max_attempts, result=result)
            if config.on_success is not None:
                config.on_success(last_state)
            return result
        except BaseException as exc:  # noqa: BLE001
            last_state = RetryState(attempt=attempt, max_attempts=config.max_attempts, exception=exc)
            if attempt >= config.max_attempts or not _should_retry(config, exc=exc):
                if config.on_failure is not None:
                    config.on_failure(last_state)
                raise
            delay = _compute_delay(config, attempt)
            last_state.delay = delay
            if config.on_retry is not None:
                config.on_retry(last_state)
            await _sleep(delay)
    if config.on_failure is not None:
        config.on_failure(last_state)
    raise RuntimeError("retry exhausted")


def _sync_retry_call(func: Callable[..., Any], config: RetryConfig, *args: Any, **kwargs: Any) -> Any:
    last_state = RetryState(attempt=1, max_attempts=config.max_attempts)
    for attempt in range(1, config.max_attempts + 1):
        try:
            result = func(*args, **kwargs)
            if attempt < config.max_attempts and _should_retry(config, value=result):
                delay = _compute_delay(config, attempt)
                last_state = RetryState(attempt=attempt, max_attempts=config.max_attempts, result=result, delay=delay)
                if config.on_retry is not None:
                    config.on_retry(last_state)
                sleep(delay)
                continue
            last_state = RetryState(attempt=attempt, max_attempts=config.max_attempts, result=result)
            if config.on_success is not None:
                config.on_success(last_state)
            return result
        except BaseException as exc:  # noqa: BLE001
            last_state = RetryState(attempt=attempt, max_attempts=config.max_attempts, exception=exc)
            if attempt >= config.max_attempts or not _should_retry(config, exc=exc):
                if config.on_failure is not None:
                    config.on_failure(last_state)
                raise
            delay = _compute_delay(config, attempt)
            last_state.delay = delay
            if config.on_retry is not None:
                config.on_retry(last_state)
            sleep(delay)
    if config.on_failure is not None:
        config.on_failure(last_state)
    raise RuntimeError("retry exhausted")


def retry(config: RetryConfig | None = None) -> Callable[[F], F]:
    retrying = Retrying(config)

    def decorator(func: F) -> F:
        return retrying.wrap(func)

    return decorator
