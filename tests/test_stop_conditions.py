from retrio import RetryConfig, Retrying, stop_after_attempt, stop_after_delay, stop_any


def test_stop_after_attempt_short_circuits_retry() -> None:
    calls = {"count": 0}

    retrying = Retrying(
        RetryConfig(
            max_attempts=5,
            initial_delay=0.0,
            max_delay=0.0,
            jitter="none",
            retry_on_result=lambda value: value == "retry",
            stop_condition=stop_after_attempt(2),
        )
    )

    @retrying.wrap
    def work() -> str:
        calls["count"] += 1
        return "retry"

    assert work() == "retry"
    assert calls["count"] == 2


def test_stop_after_delay_uses_elapsed_time() -> None:
    calls = {"count": 0}

    retrying = Retrying(
        RetryConfig(
            max_attempts=5,
            initial_delay=0.0,
            max_delay=0.0,
            jitter="none",
            retry_on_result=lambda value: value == "retry",
            stop_condition=stop_any(stop_after_delay(0.0), stop_after_attempt(5)),
        )
    )

    @retrying.wrap
    def work() -> str:
        calls["count"] += 1
        return "retry"

    assert work() == "retry"
    assert calls["count"] == 1