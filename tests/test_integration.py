import pytest

from retrio import retry, RetryConfig, CircuitBreaker, TokenBucket


def test_limiter_blocks_immediate_attempt():
    limiter = TokenBucket(capacity=1.0, refill_rate=0.0)

    @retry(RetryConfig(max_attempts=2, rate_limiter=limiter))
    def work():
        return "ok"

    # first call consumes the token
    assert work() == "ok"

    with pytest.raises(RuntimeError) as exc:
        work()
    assert "rate limited" in str(exc.value)


def test_breaker_opens_and_subsequent_calls_fail_fast():
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

    @retry(RetryConfig(max_attempts=1, circuit_breaker=cb))
    def always_fail():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        always_fail()

    # circuit now open; next call should raise circuit open
    with pytest.raises(RuntimeError) as exc:
        always_fail()
    assert "circuit open" in str(exc.value)


def test_combined_limiter_breaker_flow():
    limiter = TokenBucket(capacity=3.0, refill_rate=0.0)
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

    calls = {"n": 0}

    @retry(RetryConfig(max_attempts=3, rate_limiter=limiter, circuit_breaker=cb))
    def flaky():
        calls["n"] += 1
        if calls["n"] <= 2:
            raise RuntimeError("boom")
        return "ok"

    # First call will fail twice then succeed on third attempt
    assert flaky() == "ok"

    # now break the circuit: simulate external failures by recording them
    cb.record_failure()
    cb.record_failure()

    # circuit should be open now and calls should fail fast
    with pytest.raises(RuntimeError) as exc:
        flaky()
    msg = str(exc.value)
    assert ("circuit open" in msg) or ("rate limited" in msg)
