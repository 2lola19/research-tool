from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from math import ceil
from threading import Lock


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class InMemoryRateLimiter:
    """Bounded process-local limiter for low-volume sensitive endpoints.

    This is deliberately not presented as a distributed production limiter. A deployment with
    multiple API replicas must enforce the same policy at the edge or with a shared store.
    """

    def __init__(
        self,
        *,
        max_requests: int,
        window_seconds: int,
        max_keys: int = 10_000,
    ) -> None:
        if max_requests < 1 or window_seconds < 1 or max_keys < 1:
            raise ValueError("rate-limit bounds must be positive")
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._max_keys = max_keys
        self._events: dict[str, deque[float]] = {}
        self._lock = Lock()

    def check(self, key: str, *, now: float | None = None) -> RateLimitDecision:
        normalized_key = key.strip() or "unknown"
        current = time.monotonic() if now is None else now
        cutoff = current - self._window_seconds
        with self._lock:
            events = self._events.setdefault(normalized_key, deque())
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self._max_requests:
                retry_after = max(1, ceil(events[0] + self._window_seconds - current))
                return RateLimitDecision(False, 0, retry_after)
            events.append(current)
            self._evict_if_needed()
            return RateLimitDecision(
                True,
                self._max_requests - len(events),
                0,
            )

    def _evict_if_needed(self) -> None:
        if len(self._events) <= self._max_keys:
            return
        oldest_key = min(
            self._events,
            key=lambda candidate: (
                self._events[candidate][-1] if self._events[candidate] else float("inf")
            ),
        )
        self._events.pop(oldest_key, None)
