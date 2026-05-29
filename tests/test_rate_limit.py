import time

from retrio._rate_limit import TokenBucket


def test_token_bucket_allows_and_blocks():
    bucket = TokenBucket(capacity=2.0, refill_rate=1.0)

    assert bucket.allow()
    assert bucket.allow()
    # third immediate should be denied
    assert not bucket.allow()

    # wait for refill
    time.sleep(1.05)
    assert bucket.allow()
