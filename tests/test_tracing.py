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

    def start_as_current_span(self, name, attributes=None):
        # return a dummy context manager
        span = FakeSpan()

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
