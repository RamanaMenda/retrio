from retrio._datadog import DatadogAdapter


class FakeSpan:
    def __init__(self):
        self.tags = {}
        self.finished = False

    def set_tag(self, k, v):
        self.tags[k] = v

    def finish(self):
        self.finished = True


class FakeTracer:
    def __init__(self):
        self.spans = []

    def trace(self, name):
        span = FakeSpan()
        self.spans.append((name, {}))
        # store attributes in the second element for tests
        self.spans[-1] = (name, self.spans[-1][1])
        return span


class FakeStatsd:
    def __init__(self):
        self.counts = {}
        self.timings = {}

    def increment(self, name):
        self.counts[name] = self.counts.get(name, 0) + 1

    def timing(self, name, value):
        self.timings.setdefault(name, []).append(value)


def test_datadog_adapter_reports_metrics_and_traces():
    tracer = FakeTracer()
    statsd = FakeStatsd()
    adapter = DatadogAdapter(tracer=tracer, statsd=statsd, prefix="retrio")

    class S:
        attempt = 1
        max_attempts = 2
        delay = 0.2
        elapsed = 0.5
        exception = None
        result = None

    adapter.on_event("attempt_start", S())
    adapter.on_event("retry_scheduled", S())
    adapter.on_event("attempt_failure", S())
    adapter.on_event("retry_exhausted", S())

    assert statsd.counts.get("retrio.attempts", 0) == 1
    assert statsd.counts.get("retrio.retries", 0) == 1
    assert statsd.counts.get("retrio.failures", 0) == 1
    assert statsd.counts.get("retrio.exhausted", 0) == 1
    assert statsd.timings.get("retrio.delay_ms", [])[0] == int(0.2 * 1000)