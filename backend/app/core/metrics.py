import logging
import time
from uuid import uuid4

from prometheus_client import Counter, Gauge, Histogram
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import request_id_context, sanitize_request_id

requests = Counter(
    "devicemesh_http_requests_total",
    "Completed HTTP requests",
    ["method", "route", "status"],
)
request_duration = Histogram(
    "devicemesh_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "route"],
)
ws_connections = Gauge("devicemesh_ws_connections", "Connected event stream clients")
worker_runs = Counter(
    "devicemesh_worker_runs_total",
    "Background job iterations",
    ["job", "outcome"],
)
worker_leader = Gauge(
    "devicemesh_worker_leader",
    "1 while this worker owns the scheduler advisory lock",
)
worker_last_success = Gauge(
    "devicemesh_worker_last_success_timestamp_seconds",
    "Unix timestamp of the latest successful job iteration",
    ["job"],
)
retention_deleted = Counter(
    "devicemesh_retention_deleted_rows_total",
    "Rows deleted by data retention",
    ["dataset"],
)
retention_rollups = Counter(
    "devicemesh_retention_rollups_touched_total",
    "Hourly telemetry rollups created or updated by retention",
)
ingestion = Counter(
    "devicemesh_agents_ingestion_total",
    "Accepted agent messages",
    ["kind"],
)
db_query_duration = Histogram("devicemesh_db_query_duration_seconds", "Database query latency")
agents_online = Gauge("devicemesh_agents_online", "Currently online devices")
probes_online = Gauge(
    "devicemesh_probes_online",
    "Enabled probes with a recent heartbeat",
)
incidents_open = Gauge("devicemesh_incidents_open", "Open synthetic incidents")
logger = logging.getLogger("devicemesh.http")


def _request_id(scope: Scope) -> str:
    raw = next(
        (value for key, value in scope.get("headers", []) if key.lower() == b"x-request-id"),
        None,
    )
    if raw is not None:
        try:
            provided = sanitize_request_id(raw.decode("ascii"))
        except UnicodeDecodeError:
            provided = None
        if provided is not None:
            return provided
    return uuid4().hex


class RequestMetricsMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = _request_id(scope)
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_context.set(request_id)
        started = time.perf_counter()
        status_code = 500

        async def send_with_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message["headers"] = list(message.get("headers", [])) + [
                    (b"x-request-id", request_id.encode()),
                    (b"x-content-type-options", b"nosniff"),
                ]
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            route = getattr(scope.get("route"), "path", "unmatched")
            method = (
                scope["method"]
                if scope["method"]
                in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}
                else "OTHER"
            )
            if route != "/metrics":
                requests.labels(method, route, str(status_code)).inc()
                request_duration.labels(method, route).observe(time.perf_counter() - started)
                if status_code < 300 and route in {
                    "/api/v1/agents/heartbeat",
                    "/api/v1/agents/telemetry",
                }:
                    ingestion.labels(route.rsplit("/", 1)[-1]).inc()
                logger.info(
                    "request completed",
                    extra={"route": route, "status": status_code},
                )
            request_id_context.reset(token)
