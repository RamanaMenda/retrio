# Migration from Tenacity

Retrio provides a smaller API surface with composable primitives. To map common Tenacity patterns:

- Tenacity `wait_exponential` → Retrio `WaitPolicy` via `exponential_wait(initial_delay, multiplier, max_delay, jitter, random)`.
- Tenacity `retry_if_exception_type` → Retrio `retry_if_exception_type`.
- Tenacity stop conditions (`stop_after_attempt`, `stop_after_delay`) → Retrio `stop_after_attempt`, `stop_after_delay` in `retrio._policies`.

Recipe example

```
from retrio import Retrying, RetryConfig, retry_if_exception_type, exponential_wait

retrying = Retrying(RetryConfig(
    retry_predicate=retry_if_exception_type(IOError),
    wait_policy=exponential_wait(0.1, 2.0, 5.0, "equal", random=__import__('random').random),
))

@retrying.wrap
def work():
    ...
```

Notes
- Retrio's defaults preserve common Tenacity behaviors; use the policy primitives for exact parity.
