# Usage

Basic synchronous retry

```python
from retrio import retry, RetryConfig

@retry(RetryConfig(max_attempts=3, initial_delay=0.1))
def work(x):
    # perform work that may transiently fail
    return x

work(1)
```

Async retry

```python
import asyncio
from retrio import retry, RetryConfig

@retry(RetryConfig(max_attempts=3))
async def awork(x):
    return x

asyncio.run(awork(1))
```

Observability

- Provide `on_event`, `on_retry`, `on_success`, `on_failure` callbacks in `RetryConfig` to receive lifecycle events.
- Optional adapters: OpenTelemetry and Prometheus (extras `otel` and `prometheus`).
