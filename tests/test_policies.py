from retrio import (
    RetryConfig,
    RetryPredicate,
    Retrying,
    chain_wait_policies,
    constant_wait,
    retry_any,
    retry_if_result,
)


def test_custom_retry_predicate_can_drive_retries() -> None:
    calls = {"count": 0}
    retrying = Retrying(
        RetryConfig(
            max_attempts=3,
            initial_delay=0.0,
            max_delay=0.0,
            jitter="none",
            retry_predicate=RetryPredicate(
                lambda state, value=None, exc=None: state.attempt < 3,
                name="first_two_attempts",
            ),
        )
    )

    @retrying.wrap
    def work() -> str:
        calls["count"] += 1
        return "ok"

    assert work() == "ok"
    assert calls["count"] == 3


def test_composable_wait_policies_are_applied() -> None:
    delays = []

    def on_retry(state) -> None:
        delays.append(state.delay)

    retrying = Retrying(
        RetryConfig(
            max_attempts=2,
            initial_delay=0.0,
            max_delay=0.0,
            jitter="none",
            retry_on_result=lambda value: value == "retry",
            wait_policy=chain_wait_policies(constant_wait(0.25), constant_wait(0.75)),
            on_retry=on_retry,
        )
    )

    @retrying.wrap
    def work() -> str:
        return "retry"

    assert work() == "retry"
    assert delays == [1.0]


def test_retry_any_helper_combines_predicates() -> None:
    predicate = retry_any(
        retry_if_result(lambda value: value == "retry"),
        RetryPredicate(lambda state, value=None, exc=None: state.attempt == 1, name="first_attempt"),
    )

    assert predicate(type("State", (), {"attempt": 1})(), "ok", None) is True
    assert predicate(type("State", (), {"attempt": 2})(), "retry", None) is True
    assert predicate(type("State", (), {"attempt": 2})(), "ok", None) is False