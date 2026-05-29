from retrio import retry, RetryConfig, TokenBucket, CircuitBreaker


def main() -> None:
    limiter = TokenBucket(capacity=1.0, refill_rate=0.5)
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=5.0)

    @retry(RetryConfig(max_attempts=3, initial_delay=0.1, rate_limiter=limiter, circuit_breaker=cb))
    def do_work(x: int) -> str:
        """Example sync function that fails for small x values."""
        if x < 2:
            raise RuntimeError("simulated transient error")
        return f"result={x}"

    for i in range(4):
        try:
            print("call", i, "=>", do_work(i))
        except Exception as exc:
            print("call", i, "failed:", exc)


if __name__ == "__main__":
    main()
