# Retrio Architecture

Retrio is designed around a small set of composable primitives so users can
express production-grade retry policies without forking the core engine.

Core components
- `Retrying` — execution harness that runs sync or async callables with parity.
- `RetryConfig` — surface for default behaviors and extension points.
- Policy primitives (in `retrio._policies`): `RetryPredicate`, `WaitPolicy`, `StopCondition`.
- Resilience gates: `CircuitBreaker` and `TokenBucket` rate limiter.
- Observability adapters: OpenTelemetry and Prometheus adapters that consume lifecycle events.

Design goals
- Keep the public API small and stable while allowing rich composition via policies.
- Preserve default behavior for existing users; new primitives are opt-in.
- Make observability first-class but optional at runtime to avoid heavy dependencies.

Execution flow
1. Rate limiter gate (if configured)
2. Circuit breaker gate (if configured)
3. Attempt execution
4. Evaluate retry predicates and stop conditions
5. Schedule backoff using the active wait policy
6. Emit observability events at each lifecycle point

This layering ensures predictable interactions: rate limiting prevents overload, the circuit breaker prevents futile retries, and stop conditions provide time/budget-bound early exits.
