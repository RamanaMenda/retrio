from retrio._metrics import PrometheusAdapter


class FakeCounter:
    def __init__(self):
        self.value = 0

    def inc(self):
        self.value += 1


class FakeHistogram:
    def __init__(self):
        self.values = []

    def observe(self, v):
        self.values.append(v)


def test_prometheus_adapter_counts_and_observes():
    attempts = FakeCounter()
    retries = FakeCounter()
    failures = FakeCounter()
    exhausted = FakeCounter()
    delay_hist = FakeHistogram()

    adapter = PrometheusAdapter(
        attempts_counter=attempts,
        retries_counter=retries,
        failures_counter=failures,
        exhausted_counter=exhausted,
        delay_histogram=delay_hist,
    )

    class S:
        attempt = 1
        max_attempts = 3
        delay = 0.5

    adapter.on_event("attempt_start", S())
    adapter.on_event("retry_scheduled", S())
    adapter.on_event("attempt_failure", S())
    adapter.on_event("retry_exhausted", S())

    assert attempts.value == 1
    assert retries.value == 1
    assert failures.value == 1
    assert exhausted.value == 1
    assert delay_hist.values == [0.5]
