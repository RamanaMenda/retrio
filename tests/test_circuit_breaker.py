import time

from retrio._circuit_breaker import CircuitBreaker


def test_circuit_opens_and_recovers():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.05, half_open_successes=1)

    # two failures should open
    cb.record_failure()
    assert not cb.is_open()
    cb.record_failure()
    assert cb.is_open()

    # after recovery timeout, it should allow (transition to half-open)
    time.sleep(0.06)
    assert not cb.is_open()

    # one success in half-open closes it
    cb.record_success()
    assert not cb.is_open()
