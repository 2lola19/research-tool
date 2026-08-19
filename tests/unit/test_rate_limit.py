from backend.app.core.rate_limit import InMemoryRateLimiter


def test_process_local_rate_limiter_returns_bounded_retry_window() -> None:
    limiter = InMemoryRateLimiter(max_requests=2, window_seconds=10)

    first = limiter.check("client", now=100.0)
    second = limiter.check("client", now=101.0)
    blocked = limiter.check("client", now=102.0)
    after_window = limiter.check("client", now=110.001)

    assert first.allowed is True
    assert first.remaining == 1
    assert second.allowed is True
    assert second.remaining == 0
    assert blocked.allowed is False
    assert blocked.retry_after_seconds == 8
    assert after_window.allowed is True
