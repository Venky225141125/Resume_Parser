"""JSON-structured logging. Do not log resume body or PII fields."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


_SENSITIVE_KEYS = frozenset(
    {
        "resume",
        "text",
        "content",
        "body",
        "email",
        "phone",
        "raw",
        "file_bytes",
        "api_key",
        "authorization",
        "llm_api_key",
    }
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(_redact(extra))
        return json.dumps(payload, default=str)


def _redact(fields: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in fields.items():
        if key.lower() in _SENSITIVE_KEYS:
            cleaned[key] = "[redacted]"
        else:
            cleaned[key] = value
    return cleaned


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level.upper())
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def log_event(logger: logging.Logger, message: str, **fields: Any) -> None:
    logger.info(message, extra={"extra_fields": fields})
