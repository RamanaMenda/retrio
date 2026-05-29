from retrio._tracing import OpenTelemetryAdapter


class FakeSpan:
    def __init__(self):
        self.ended = False

    def set_attribute(self, k, v):
        setattr(self, k, v)

    def end(self):
        self.ended = True


class FakeTracer:
    def __init__(self):
        self.started = []
        self.span = None

    def start_as_current_span(self, name, attributes=None):
        # return a dummy context manager
        span = FakeSpan()
        self.span = span

        class Ctx:
            def __enter__(self_non):
                self.started.append((name, attributes))
                return span

            def __exit__(self_non, exc_type, exc, tb):
                span.end()

        return Ctx()


def test_ot_adapter_starts_and_ends_spans():
    tracer = FakeTracer()
    adapter = OpenTelemetryAdapter(tracer)

    class S:
        attempt = 1
        max_attempts = 2

    adapter.on_event("attempt_start", S())
    adapter.on_event("attempt_success", S())
    assert tracer.started


def test_ot_adapter_sets_rich_attributes_on_span():
    tracer = FakeTracer()
    adapter = OpenTelemetryAdapter(tracer)

    class S:
        attempt = 2
        max_attempts = 4
        delay = 0.5
        elapsed = 1.25
        result = "ok"
        exception = None

    adapter.on_event("attempt_start", S())
    adapter.on_event("attempt_success", S())

    assert tracer.started[0][1]["retrio.attempt"] == 2
    assert tracer.started[0][1]["retrio.max_attempts"] == 4
    assert getattr(tracer.span, "retrio.event", None) == "attempt_success"
    assert getattr(tracer.span, "retrio.attempt", None) == 2
    assert getattr(tracer.span, "retrio.result_type", None) == "str"
