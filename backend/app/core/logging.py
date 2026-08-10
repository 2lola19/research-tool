from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import ClassVar
from uuid import uuid4


class RequestIdContext:
    def __init__(self) -> None:
        self._value: ContextVar[str] = ContextVar("request_id", default="system")

    def new_id(self) -> str:
        return str(uuid4())

    def get(self) -> str:
        return self._value.get()

    def set(self, value: str) -> Token[str]:
        return self._value.set(value)

    def reset(self, token: Token[str]) -> None:
        self._value.reset(token)


request_id_context = RequestIdContext()


class JsonFormatter(logging.Formatter):
    _standard_attributes: ClassVar[set[str]] = set(logging.makeLogRecord({}).__dict__)

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_context.get(),
        }
        for key, value in record.__dict__.items():
            if key not in self._standard_attributes and key not in {"message", "asctime"}:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=level, handlers=[handler], force=True)
