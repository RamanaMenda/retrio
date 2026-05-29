# Retrio

Retrio is a small Python retry and backoff toolkit with sync and async support, jitter, result-based retries, and observability hooks.

## Install

```bash
pip install retrio
```

## Example

```python
from retrio import RetryConfig, retry

attempts = {"count": 0}

@retry(RetryConfig(max_attempts=3))
def fetch_value() -> str:
    attempts["count"] += 1
    if attempts["count"] < 3:
        raise RuntimeError("try again")
    return "ok"

print(fetch_value())
```

## Lifecycle Events

Retrio emits consistent lifecycle events for both sync and async functions:

- `attempt_start`
- `retry_scheduled`
- `attempt_success`
- `attempt_failure`
- `retry_exhausted`

You can subscribe with `on_event`:

```python
from retrio import RetryConfig, retry


def on_event(event, state) -> None:
    print(event, state.attempt, state.max_attempts)


@retry(
    RetryConfig(
        max_attempts=3,
        on_event=on_event,
    )
)
def work() -> str:
    raise RuntimeError("boom")


try:
    work()
except RuntimeError:
    pass
```

## Beautiful Logging

Retrio supports two built-in log styles:

- `pretty`: readable, human-friendly messages
- `structured`: key=value records for log ingestion

```python
import logging

from retrio import RetryConfig, retry

logger = logging.getLogger("retrio.app")
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())


@retry(
    RetryConfig(
        max_attempts=3,
        enable_logging=True,
        logger=logger,
        log_style="structured",
    )
)
def fetch() -> str:
    raise RuntimeError("transient")


## Resilience Features

Retrio includes simple resilience building blocks you can opt into via `RetryConfig`:

- `CircuitBreaker` — a small thread-safe circuit breaker (closed/open/half-open).
- `TokenBucket` — a token-bucket rate limiter for graceful throttling.

Examples

Circuit breaker example:

```python
from retrio import retry, RetryConfig, CircuitBreaker

cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)

@retry(RetryConfig(max_attempts=3, circuit_breaker=cb))
def unreliable() -> str:
    raise RuntimeError("transient")

try:
    unreliable()
except RuntimeError:
    print("operation failed and recorded by circuit breaker")

# after repeated failures, cb.is_open() becomes True and further calls fail fast
```

Rate limiter example:

```python
from retrio import retry, RetryConfig, TokenBucket

limiter = TokenBucket(capacity=2, refill_rate=0.5)  # 2 tokens, 0.5 tokens/sec

@retry(RetryConfig(max_attempts=2, rate_limiter=limiter))
def send_request() -> str:
    return "ok"

print(send_request())
```

Combined behavior

You can combine the two; the `RetryConfig` checks the rate limiter and circuit breaker before each attempt. If the limiter denies the attempt, the retry raises a `RuntimeError("rate limited")`. If the circuit is open, it raises `RuntimeError("circuit open")` to fail fast.

```python
try:
    fetch()
except RuntimeError:
    pass
```

## Datadog Integration

Retrio provides a `DatadogAdapter` for reporting retry attempts and metrics to Datadog. The adapter accepts an optional `ddtrace` tracer and a `dogstatsd`/`statsd` client and operates in a best-effort manner if those libraries are not installed.

Example (see `examples/datadog_example.py`):

```python
from retrio import retry, RetryConfig, DatadogAdapter

adapter = DatadogAdapter(tracer=None, statsd=None)  # replace with real clients

@retry(RetryConfig(max_attempts=3, on_event=adapter.on_event))
def work():
    ...
```

