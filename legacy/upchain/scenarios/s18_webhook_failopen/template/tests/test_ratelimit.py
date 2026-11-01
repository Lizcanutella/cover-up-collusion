import pytest

from comms.ratelimit import RateLimited, TokenBucket
from tests.helpers.fakes import FakeClock


def test_burst_then_refill():
    clock = FakeClock(0)
    bucket = TokenBucket(per_minute=30, clock=clock)
    for _ in range(5):
        bucket.take("+447700900123")
    with pytest.raises(RateLimited) as info:
        bucket.take("+447700900123")
    assert info.value.retry_after == pytest.approx(2.0)
    clock.advance(2)
    bucket.take("+447700900123")


def test_buckets_are_per_recipient():
    bucket = TokenBucket(per_minute=6, clock=FakeClock(0))
    bucket.take("+447700900123")
    bucket.take("+447700900456")
