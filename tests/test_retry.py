from retrio import RetryConfig, Retrying, retry


def test_sync_retry_succeeds_after_failures() -> None:
    calls = {"count": 0}

    @retry(RetryConfig(max_attempts=3, initial_delay=0.0, max_delay=0.0, jitter="none"))
    def work() -> str:
        calls["count"] += 1
        if calls["count"] < 3:
            raise ValueError("boom")
        return "ok"

    assert work() == "ok"
    assert calls["count"] == 3


def test_async_retry_succeeds_after_failures() -> None:
    calls = {"count": 0}

    @retry(RetryConfig(max_attempts=3, initial_delay=0.0, max_delay=0.0, jitter="none"))
    async def work() -> str:
        calls["count"] += 1
        if calls["count"] < 3:
            raise ValueError("boom")
        return "ok"

    async def run() -> None:
        assert await work() == "ok"

    import asyncio

    asyncio.run(run())
    assert calls["count"] == 3


def test_result_based_retry() -> None:
    calls = {"count": 0}

    @retry(
        RetryConfig(
            max_attempts=3,
            initial_delay=0.0,
            max_delay=0.0,
            jitter="none",
            retry_on_result=lambda value: value == "retry",
        )
    )
    def work() -> str:
        calls["count"] += 1
        return "retry" if calls["count"] < 3 else "ok"

    assert work() == "ok"
    assert calls["count"] == 3


def test_observability_hooks_receive_state() -> None:
    states = []

    def on_retry(state):
        states.append((state.attempt, state.delay, state.exception is not None))

    @retry(RetryConfig(max_attempts=2, initial_delay=0.0, max_delay=0.0, jitter="none", on_retry=on_retry))
    def work() -> str:
        raise ValueError("boom")

    try:
        work()
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")

    assert states == [(1, 0.0, True)]


def test_wrapper_helper_api() -> None:
    calls = {"count": 0}

    retrying = Retrying(RetryConfig(max_attempts=2, initial_delay=0.0, max_delay=0.0, jitter="none"))

    def work() -> str:
        calls["count"] += 1
        if calls["count"] < 2:
            raise ValueError("boom")
        return "ok"

    assert retrying.call(work) == "ok"
    assert calls["count"] == 2
