# Observability

Retrio emits lifecycle events for every retry attempt which adapters can
consume for tracing and metrics. The event contract is stable and includes:

- `event`: one of `attempt_start`, `retry_scheduled`, `attempt_success`, `attempt_failure`, `retry_exhausted`
- `attempt`, `max_attempts`, `delay`, `elapsed`
- `outcome` (`start`, `retry`, `success`, `failure`, `exhausted`)
- `exception_type` and `result_type` where applicable

Logging
- `RetryConfig(log_style="pretty"|"structured"|"json")` controls the logger output.
- `json` emits a machine-readable JSON object with the fields above.

OpenTelemetry
- Use `OpenTelemetryAdapter(tracer)` and set `config.on_event = adapter.on_event`.
- The adapter creates per-attempt spans and attaches attributes: `retrio.attempt`, `retrio.max_attempts`, `retrio.delay`, `retrio.elapsed`, `retrio.exception_type`, `retrio.result_type`.

Prometheus
- Use `PrometheusAdapter` with either `prometheus_client` on the path or pass existing `Counter`/`Histogram` objects.
- The adapter increments `attempts`, `retries`, `failures`, `exhausted` and records backoff delays.

Best practice
- Route JSON logs to a centralized log pipeline for alerting on frequent `retry_exhausted` events.
- Use tracing attributes to correlate attempts with upstream requests.
