"""Example showing Datadog tracer + statsd integration with Retrio."""
from retrio import retry, RetryConfig, DatadogAdapter


def main():
    # Replace these with real ddtrace tracer and dogstatsd client
    try:
        from ddtrace import tracer as dd_tracer
    except Exception:
        dd_tracer = None

    try:
        from datadog import DogStatsd

        statsd = DogStatsd()
    except Exception:
        statsd = None

    adapter = DatadogAdapter(tracer=dd_tracer, statsd=statsd)

    @retry(RetryConfig(max_attempts=3, on_event=adapter.on_event))
    def work(x):
        print("working", x)
        raise RuntimeError("boom")

    try:
        work(1)
    except Exception:
        print("done")


if __name__ == "__main__":
    main()
