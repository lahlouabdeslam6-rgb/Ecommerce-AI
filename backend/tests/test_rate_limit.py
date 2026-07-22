from app.core.rate_limit import MemoryRateLimiter


def test_rate_limiter_blocks_after_limit() -> None:
    limiter = MemoryRateLimiter()
    assert limiter.allow("login:127.0.0.1", limit=2, window_seconds=60)
    assert limiter.allow("login:127.0.0.1", limit=2, window_seconds=60)
    assert not limiter.allow("login:127.0.0.1", limit=2, window_seconds=60)


def test_rate_limiter_separates_keys() -> None:
    limiter = MemoryRateLimiter()
    assert limiter.allow("a", limit=1, window_seconds=60)
    assert not limiter.allow("a", limit=1, window_seconds=60)
    assert limiter.allow("b", limit=1, window_seconds=60)
