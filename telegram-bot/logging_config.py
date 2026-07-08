"""Single-line structured logging for the LifeOS bot."""

from __future__ import annotations

import json
import logging
import re
import traceback
from datetime import datetime, timezone


_TELEGRAM_TOKEN = re.compile(r"bot\d+:[A-Za-z0-9_-]+")
_AUTHORIZATION_HEADER = re.compile(
    r'''(?i)(["']?authorization["']?\s*[:=]\s*["']?)(?:bearer\s+)?[^\s,"'}]+'''
)
_BEARER_CREDENTIAL = re.compile(r"(?i)(bearer\s+)[^\s\"']+")


def _redact(value: str) -> str:
    value = _TELEGRAM_TOKEN.sub("bot[REDACTED]", value)
    value = _AUTHORIZATION_HEADER.sub(r"\1[REDACTED]", value)
    return _BEARER_CREDENTIAL.sub(r"\1[REDACTED]", value)


class JsonFormatter(logging.Formatter):
    """Serialize a log record as exactly one physical JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": _redact(record.getMessage()),
        }

        event = getattr(record, "event", None)
        if event:
            payload["event"] = _redact(str(event))

        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__
            exception = "".join(traceback.format_exception(*record.exc_info)).rstrip()
            payload["exception"] = _redact(exception)

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging() -> None:
    """Configure application logging once while preserving capture handlers."""

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    if not any(
        getattr(handler, "_lifeos_json_handler", False)
        for handler in root.handlers
    ):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        handler._lifeos_json_handler = True  # type: ignore[attr-defined]
        root.addHandler(handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
