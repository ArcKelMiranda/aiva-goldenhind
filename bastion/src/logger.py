"""Structured JSON logging for the bastion runtime."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

LOGGER_NAME = "yhat_bny_secure_sftp_ingestion"

_EXTRA_FIELDS = (
    "event",
    "status",
    "remoteFile",
    "localPath",
    "bytes",
    "correlationId",
    "error",
    "retentionDays",
    "localRoot",
    "directories",
    "downloadedFiles",
    "deletedFiles",
    "downloadedCount",
    "deletedCount",
)


class JsonFormatter(logging.Formatter):
    """Render log records as compact JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }

        for field in _EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logger(level: int | str = logging.INFO) -> logging.Logger:
    """Configure and return the shared runtime logger."""

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)

    return logger


def emit_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields: Any) -> None:
    """Log a structured event with canonical JSON field names."""

    extra = {"event": event, **fields}
    logger.log(level, event, extra=extra)
