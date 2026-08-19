from __future__ import annotations

import re
from collections import defaultdict
from threading import Lock

_UUID_PATH_SEGMENT = re.compile(
    r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}(?=/|$)"
)
_NUMERIC_PATH_SEGMENT = re.compile(r"/\d+(?=/|$)")


def safe_route_label(path: str) -> str:
    """Return a low-cardinality route label without identifiers from the URL."""

    normalized = _UUID_PATH_SEGMENT.sub("/:id", path)
    normalized = _NUMERIC_PATH_SEGMENT.sub("/:number", normalized)
    return normalized[:200] or "/"


class RequestMetrics:
    """Small dependency-free request counter for local scraping and diagnostics."""

    def __init__(self) -> None:
        self._counts: defaultdict[tuple[str, int], int] = defaultdict(int)
        self._duration_totals: defaultdict[str, float] = defaultdict(float)
        self._duration_counts: defaultdict[str, int] = defaultdict(int)
        self._lock = Lock()

    def observe(self, route: str, status_code: int, duration_ms: float) -> None:
        safe_route = safe_route_label(route)
        with self._lock:
            self._counts[(safe_route, status_code)] += 1
            self._duration_totals[safe_route] += max(0.0, duration_ms)
            self._duration_counts[safe_route] += 1

    def render_prometheus(self) -> str:
        with self._lock:
            counts = dict(self._counts)
            durations = dict(self._duration_totals)
            duration_counts = dict(self._duration_counts)

        lines = [
            "# HELP review_http_requests_total HTTP requests completed by route and status.",
            "# TYPE review_http_requests_total counter",
        ]
        for (route, status_code), count in sorted(counts.items()):
            lines.append(
                f'review_http_requests_total{{route="{_escape(route)}",status="{status_code}"}} '
                f"{count}"
            )
        lines.extend(
            [
                "# HELP review_http_request_duration_ms_sum Total request duration "
                "in milliseconds.",
                "# TYPE review_http_request_duration_ms_sum counter",
            ]
        )
        for route, total in sorted(durations.items()):
            lines.append(
                f'review_http_request_duration_ms_sum{{route="{_escape(route)}"}} {total:.3f}'
            )
        lines.extend(
            [
                "# HELP review_http_request_duration_ms_count Requests included in "
                "duration totals.",
                "# TYPE review_http_request_duration_ms_count counter",
            ]
        )
        for route, count in sorted(duration_counts.items()):
            lines.append(
                f'review_http_request_duration_ms_count{{route="{_escape(route)}"}} {count}'
            )
        return "\n".join(lines) + "\n"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "")
