import json
import logging
import re
from contextvars import ContextVar, Token
from datetime import UTC, datetime

request_id_context: ContextVar[str] = ContextVar("request_id", default="")
log_context: ContextVar[dict[str, object] | None] = ContextVar("log_context", default=None)

_service_name = "devicemesh"
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_CONTEXT_FIELDS = (
    "device_id",
    "incident_id",
    "monitor_id",
    "probe_id",
    "service_id",
    "job",
    "status",
    "route",
)


def sanitize_request_id(value: str | None) -> str | None:
    """Return a safe caller-provided correlation ID, or None when it must be replaced."""
    if value is None or not _REQUEST_ID_RE.fullmatch(value):
        return None
    return value


def bind_log_context(**fields: object) -> Token[dict[str, object] | None]:
    """Bind safe domain fields to the current async/thread context."""
    current = log_context.get() or {}
    accepted = {
        key: value
        for key, value in fields.items()
        if key in _CONTEXT_FIELDS and value is not None
    }
    return log_context.set({**current, **accepted})


def reset_log_context(token: Token[dict[str, object] | None]) -> None:
    log_context.reset(token)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": getattr(record, "service", _service_name),
            "component": record.name,
            "process_id": record.process,
            "request_id": getattr(record, "request_id", request_id_context.get()),
            "message": record.getMessage(),
        }
        # Deliberately exclude headers, query strings, bodies and exception messages:
        # database URLs and bearer credentials can occur in those values.
        if record.exc_info and record.exc_info[0]:
            data["exception_type"] = record.exc_info[0].__name__
        context = log_context.get() or {}
        for field in _CONTEXT_FIELDS:
            if hasattr(record, field):
                data[field] = getattr(record, field)
            elif field in context:
                data[field] = context[field]
        return json.dumps(data, ensure_ascii=False)


def configure_logging(service_name: str = "devicemesh", level: int = logging.INFO) -> None:
    """Install one JSON logger for DeviceMesh and third-party process loggers."""
    global _service_name
    _service_name = service_name

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # DeviceMesh emits its own access record without raw URLs/query strings.
    logging.getLogger("uvicorn.access").disabled = True
    for logger_name in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = True
