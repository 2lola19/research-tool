import json
import logging

from backend.app.core.logging import JsonFormatter, request_id_context


def test_json_logging_contains_request_context() -> None:
    token = request_id_context.set("request-123")
    try:
        output = JsonFormatter().format(logging.makeLogRecord({"msg": "hello", "levelno": 20}))
    finally:
        request_id_context.reset(token)

    parsed = json.loads(output)
    assert parsed["message"] == "hello"
    assert parsed["request_id"] == "request-123"
