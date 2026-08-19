import json
import logging

from backend.app.core.logging import (
    JsonFormatter,
    normalize_request_id,
    request_id_context,
    trace_id_context,
    trace_id_from_header,
)


def test_json_logging_contains_request_context() -> None:
    token = request_id_context.set("request-123")
    try:
        output = JsonFormatter().format(logging.makeLogRecord({"msg": "hello", "levelno": 20}))
    finally:
        request_id_context.reset(token)

    parsed = json.loads(output)
    assert parsed["message"] == "hello"
    assert parsed["request_id"] == "request-123"


def test_correlation_headers_are_bounded_and_traceparent_is_reused() -> None:
    assert normalize_request_id("request-123") == "request-123"
    generated = normalize_request_id("bad\nvalue")
    assert len(generated) == 36
    assert trace_id_from_header("00-0123456789abcdef0123456789abcdef-0123456789abcdef-01") == (
        "0123456789abcdef0123456789abcdef"
    )

    request_token = request_id_context.set("request-123")
    trace_token = trace_id_context.set("trace-123")
    try:
        parsed = json.loads(JsonFormatter().format(logging.makeLogRecord({"msg": "hello"})))
    finally:
        trace_id_context.reset(trace_token)
        request_id_context.reset(request_token)
    assert parsed["trace_id"] == "trace-123"
