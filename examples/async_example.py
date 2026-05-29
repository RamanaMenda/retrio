import asyncio

from retrio import retry, RetryConfig


async def main() -> None:
    @retry(RetryConfig(max_attempts=4, initial_delay=0.1))
    async def flaky(i: int) -> str:
        # simulate an async operation which occasionally fails
        await asyncio.sleep(0.01)
        if i % 3 != 0:
            raise RuntimeError("transient")
        return f"ok-{i}"

    for i in range(6):
        try:
            print("async call", i, "=>", await flaky(i))
        except Exception as exc:
            print("async call", i, "failed:", exc)


if __name__ == "__main__":
    asyncio.run(main())
