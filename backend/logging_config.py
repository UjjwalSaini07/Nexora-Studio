import json
import logging
import sys
from datetime import datetime, timezone

from config import LOG_LEVEL, ENVIRONMENT


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        # Allow callers to pass structured extras via `extra={"ctx": {...}}`
        if hasattr(record, "ctx"):
            payload["ctx"] = record.ctx
        return json.dumps(payload, default=str)


class DevFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[41m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        base = f"{color}[{record.levelname:<8}]{self.RESET} {record.name}: {record.getMessage()}"
        if hasattr(record, "ctx"):
            base += f" | ctx={record.ctx}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def configure_logging() -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    if ENVIRONMENT == "production":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(DevFormatter())
    root.addHandler(handler)
    root.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    # Quiet noisy third-party loggers unless we're debugging
    for noisy in ("httpx", "httpcore", "pymongo", "motor"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
