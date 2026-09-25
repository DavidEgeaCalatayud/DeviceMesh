import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_context: ContextVar[str] = ContextVar("request_id", default="")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "component": record.name,
            "request_id": request_id_context.get(),
            "message": record.getMessage(),
        }
        # Deliberately exclude headers, query strings, bodies and exception messages:
        # database URLs and bearer credentials can occur in those values.
        if record.exc_info and record.exc_info[0]:
            data["exception_type"] = record.exc_info[0].__name__
        for field in ("device_id", "incident_id", "monitor_id", "probe_id", "status", "route"):
            if hasattr(record, field):
                data[field] = getattr(record, field)
        return json.dumps(data, ensure_ascii=False)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])
