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


try:
    fetch()
except RuntimeError:
    pass
```
