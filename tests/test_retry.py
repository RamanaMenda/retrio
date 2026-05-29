import logging

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


def test_sync_event_hook_sequence() -> None:
    calls = {"count": 0}
    events = []

    def on_event(event, state) -> None:
        events.append((event, state.attempt))

    @retry(
        RetryConfig(
            max_attempts=2,
            initial_delay=0.0,
            max_delay=0.0,
            jitter="none",
            on_event=on_event,
        )
    )
    def work() -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            raise ValueError("boom")
        return "ok"

    assert work() == "ok"
    assert events == [
        ("attempt_start", 1),
        ("attempt_failure", 1),
        ("retry_scheduled", 1),
        ("attempt_start", 2),
        ("attempt_success", 2),
    ]


def test_structured_logging_emits_event_fields(caplog) -> None:
    calls = {"count": 0}
    logger = logging.getLogger("retrio.tests")

    @retry(
        RetryConfig(
            max_attempts=2,
            initial_delay=0.0,
            max_delay=0.0,
            jitter="none",
            logger=logger,
            enable_logging=True,
            log_style="structured",
        )
    )
    def work() -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            raise ValueError("boom")
        return "ok"

    with caplog.at_level(logging.DEBUG, logger="retrio.tests"):
        assert work() == "ok"

    messages = [record.message for record in caplog.records]
    assert any("event=retry_scheduled" in message for message in messages)
    assert any("event=attempt_success" in message for message in messages)


def test_async_event_hook_sequence() -> None:
    calls = {"count": 0}
    events = []

    def on_event(event, state) -> None:
        events.append((event, state.attempt))

    @retry(
        RetryConfig(
            max_attempts=2,
            initial_delay=0.0,
            max_delay=0.0,
            jitter="none",
            on_event=on_event,
        )
    )
    async def work() -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            raise ValueError("boom")
        return "ok"

    async def run() -> None:
        assert await work() == "ok"

    import asyncio

    asyncio.run(run())
    assert events == [
        ("attempt_start", 1),
        ("attempt_failure", 1),
        ("retry_scheduled", 1),
        ("attempt_start", 2),
        ("attempt_success", 2),
    ]
