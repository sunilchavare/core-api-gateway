import contextvars
import json
import logging
from datetime import datetime, timezone

# The correlation id of the request being handled. A ContextVar is isolated per
# request even when many requests run concurrently on one event loop.
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)

# Attributes every LogRecord has. Anything else was passed with `extra=`.
_STANDARD_ATTRIBUTES = set(
    logging.LogRecord("", logging.INFO, "", 0, "", None, None).__dict__
) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """One JSON object per line, easy for log tools to parse."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        request_id = request_id_var.get()
        if request_id:
            payload["request_id"] = request_id

        # setdefault: extra fields can add information but never replace the
        # core fields above.
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRIBUTES:
                payload.setdefault(key, value)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # default=str: a value JSON cannot encode must never crash logging.
        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # Send uvicorn's own messages through the same JSON handler, and turn off
    # its plain-text access log: the gateway writes a richer one itself.
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True
