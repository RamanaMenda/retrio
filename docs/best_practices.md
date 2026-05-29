# Best Practices

When to retry
- Retry only idempotent operations or operations that can be made idempotent.
- Prefer result-based predicates for transient semantic failures (e.g., `retry_on_result=lambda r: r.status==503`).

Rate limiting vs circuit breaking
- Use a `TokenBucket` rate limiter to enforce throughput limits and protect downstream services.
- Use a `CircuitBreaker` to avoid repeated retries during an outage; prefer conservative thresholds and progressive half-open probing.

Stop conditions
- Prefer `stop_after_delay` when you have a strict end-to-end latency budget.
- Use `stop_after_attempt` to cap retry amplification when downstream systems are fragile.

Observability
- Emit JSON logs for machine parsing; instrument `retry_exhausted` for alerting.
- Correlate retrio spans with existing request traces using OpenTelemetry context propagation.

Testing
- Add unit tests for predicate composition and stop-condition boundaries.
- Use the `Retrying(RetryConfig(...)).wrap` helper in test fixtures to exercise sync and async parity.
