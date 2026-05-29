# Benchmarks

This project aims to keep the retry hot path minimal. A small microbenchmark shows the overhead of a single synchronous attempt (no retries) is small relative to typical I/O latencies.

Recommended benchmark harness

1. Use `time.perf_counter()` around `Retrying(...).call()` for many iterations.
2. Measure both sync and async paths with realistic I/O mocks.
3. Compare with Tenacity by running identical backoff and predicate setups.

Publishing results
- Add a `benchmarks/` directory with reproducible harness and a short report in this page when ready.
