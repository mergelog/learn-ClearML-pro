"""Structured logging, and the identifiers that make lines relatable.

A log line that says "the request failed" is worth very little in a system
where a prediction, the model that answered it, the run that produced that
model and the Dataset it learned from are four different things in four
different places.

So every line carries the same set of identifiers, and every line is one JSON
object. Two consequences follow, and both are the point.

A person can grep for one correlation id and see the whole request. A machine
can read the same lines without a regular expression that breaks the first
time somebody adds a field.

The context is deliberately per-request rather than per-process. A service
answers many callers at once, and attaching the identifiers to the process
would mix them together.

This module depends on nothing but the standard library.
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any


CORRELATION_ID_HEADER = "X-Correlation-Id"

# ログの1行に必ず入る項目。ここに無いものは、その行の固有の情報である。
TIMESTAMP_FIELD = "timestamp"
LEVEL_FIELD = "level"
MESSAGE_FIELD = "message"
LOGGER_FIELD = "logger"

# ``logging`` が LogRecord に必ず持たせる属性。ここに無い属性だけが
# 呼び出し側の付けた情報なので、その差分を JSON へ載せる。
_STANDARD_RECORD_FIELDS = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__
) | {"message", "asctime", "taskName"}


@dataclass(frozen=True)
class LogContext:
    """What every line of one unit of work carries.

    ``correlation_id`` is what ties lines together. It is generated when a
    request arrives without one, and echoed back, so a caller can quote it when
    reporting a problem.

    The remaining fields are absent until something makes them true. A line
    written before the model was loaded genuinely has no model version, and
    saying so is better than writing an empty string that reads like one.
    """

    correlation_id: str
    service: str
    model_version: str | None = None
    task_id: str | None = None
    dataset_version: str | None = None

    def as_fields(self) -> dict[str, str]:
        fields = {"correlation_id": self.correlation_id, "service": self.service}
        for name, value in (
            ("model_version", self.model_version),
            ("task_id", self.task_id),
            ("dataset_version", self.dataset_version),
        ):
            if value:
                fields[name] = value
        return fields


_CONTEXT: ContextVar[LogContext | None] = ContextVar("log_context", default=None)


def new_correlation_id() -> str:
    """A fresh identifier for one unit of work."""
    return uuid.uuid4().hex


def current_context() -> LogContext | None:
    return _CONTEXT.get()


@contextmanager
def log_context(context: LogContext) -> Iterator[LogContext]:
    """Attach identifiers to everything logged inside this block.

    The previous context is restored on the way out, including when the block
    raised, so one failed request cannot leave its identifiers on the next.
    """
    token = _CONTEXT.set(context)
    try:
        yield context
    finally:
        _CONTEXT.reset(token)


@contextmanager
def extended_context(**fields: str | None) -> Iterator[LogContext | None]:
    """Add to the current context what has only just become known.

    A request knows its model version after the model answered, not before.
    """
    current = _CONTEXT.get()
    if current is None:
        yield None
        return

    known = {name: value for name, value in fields.items() if value is not None}
    with log_context(replace(current, **known)) as extended:  # type: ignore[arg-type]
        yield extended


class StructuredFormatter(logging.Formatter):
    """Write one JSON object per line.

    Anything the caller attached with ``extra`` is written alongside, so a
    message stays a message and the values stay values. An exception is
    rendered into the same object rather than onto following lines, because a
    traceback split across lines is not one log event any more.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            TIMESTAMP_FIELD: _timestamp(record.created),
            LEVEL_FIELD: record.levelname.lower(),
            LOGGER_FIELD: record.name,
            MESSAGE_FIELD: record.getMessage(),
        }

        context = _CONTEXT.get()
        if context is not None:
            payload.update(context.as_fields())

        payload.update(_extra_fields(record))

        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: int = logging.INFO, stream: Any | None = None) -> None:
    """Send every log line to one place, in one shape.

    Existing handlers are replaced rather than added to. A process that writes
    the same event twice, once structured and once not, teaches whoever reads
    it to trust neither.
    """
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(StructuredFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


def _timestamp(created: float) -> str:
    return datetime.fromtimestamp(created, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _extra_fields(record: logging.LogRecord) -> Mapping[str, Any]:
    return {
        name: value
        for name, value in record.__dict__.items()
        if name not in _STANDARD_RECORD_FIELDS and not name.startswith("_")
    }
