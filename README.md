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
