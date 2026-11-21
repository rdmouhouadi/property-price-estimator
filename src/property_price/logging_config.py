"""Shared logging: readable console + JSON lines file, one run_id per execution."""

import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

RUN_ID = os.environ.get("RUN_ID", uuid.uuid4().hex[:8])
LOG_FILE = Path(os.environ.get("LOG_FILE", "logs/pipeline.jsonl"))


class JsonFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    Each log record is a JSON object with keys:
    - ts: timestamp in UTC, ISO 8601 format
    - level: log level
    - run_id: unique identifier for the run
    - logger: logger name
    - msg: log message
    - exc: exception info (if any)
    - extra_fields: additional fields passed via the 'extra' parameter
    """
    def format(self, record: logging.LogRecord) -> str:
        """
        Format a log record as a JSON string.
        """
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "level": record.levelname,
            "run_id": RUN_ID,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        entry.update(getattr(record, "extra_fields", {}))
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def _configure() -> None:
    """
    Configure the root logger with a console handler and an optional file handler.
    The console handler outputs human-readable logs to stdout.
    The file handler outputs structured JSON logs to a file.
    """
    root = logging.getLogger("property_price")
    if root.handlers:  # already configured
        return
    root.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(
        f"%(asctime)s %(levelname)-7s [{RUN_ID}] %(name)s: %(message)s", "%H:%M:%S"))
    root.addHandler(console)

    if os.environ.get("LOG_TO_FILE", "1") == "1":  # set 0 in Docker
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        file = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file.setFormatter(JsonFormatter())
        root.addHandler(file)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name, configured with console and file handlers.
    """
    _configure()
    return logging.getLogger(name)


def log_metric(logger: logging.Logger, msg: str, **fields) -> None:
    """
    Log a metric with structured fields.
    The metric is logged as a JSON object with keys:
    - ts: timestamp in UTC, ISO 8601 format
    - level: log level (INFO)
    - run_id: unique identifier for the run
    - logger: logger name
    - msg: log message
    - extra_fields: additional fields passed via the 'fields' parameter
    """
    logger.info(f"{msg} " + " ".join(f"{k}={v}" for k, v in fields.items()),
                extra={"extra_fields": fields})