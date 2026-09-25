import asyncio
import json
import logging

from starlette.types import Message, Receive, Scope, Send

from app.core.logging import (
    JsonFormatter,
    bind_log_context,
    request_id_context,
    reset_log_context,
    sanitize_request_id,
)
from app.core.metrics import RequestMetricsMiddleware


def test_json_formatter_includes_request_and_domain_context() -> None:
    request_token = request_id_context.set("req-123")
    context_token = bind_log_context(device_id="device-7", job="synthetics")
    try:
        record = logging.LogRecord(
            name="devicemesh.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="check completed",
            args=(),
            exc_info=None,
        )
        payload = json.loads(JsonFormatter().format(record))
    finally:
        reset_log_context(context_token)
        request_id_context.reset(request_token)

    assert payload["request_id"] == "req-123"
    assert payload["device_id"] == "device-7"
    assert payload["job"] == "synthetics"
    assert payload["component"] == "devicemesh.test"
    assert payload["process_id"] > 0


def test_request_id_validation_rejects_unsafe_values() -> None:
    assert sanitize_request_id("edge-01.trace_2") == "edge-01.trace_2"
    assert sanitize_request_id("") is None
    assert sanitize_request_id("contains spaces") is None
    assert sanitize_request_id("x" * 65) is None
    assert sanitize_request_id("token=secret&x=1") is None


def test_request_middleware_preserves_safe_correlation_id() -> None:
    sent: list[Message] = []

    async def downstream(scope: Scope, receive: Receive, send: Send) -> None:
        del receive
        assert scope["state"]["request_id"] == "edge-request-123"
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        sent.append(message)

    scope: Scope = {
        "type": "http",
        "method": "GET",
        "path": "/health",
        "headers": [(b"x-request-id", b"edge-request-123")],
        "state": {},
    }
    asyncio.run(RequestMetricsMiddleware(downstream)(scope, receive, send))

    start = next(message for message in sent if message["type"] == "http.response.start")
    assert (b"x-request-id", b"edge-request-123") in start["headers"]


def test_request_middleware_replaces_unsafe_correlation_id() -> None:
    sent: list[Message] = []

    async def downstream(scope: Scope, receive: Receive, send: Send) -> None:
        del receive
        request_id = scope["state"]["request_id"]
        assert len(request_id) == 32
        assert request_id != "unsafe request id"
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Message) -> None:
        sent.append(message)

    scope: Scope = {
        "type": "http",
        "method": "GET",
        "path": "/health",
        "headers": [(b"x-request-id", b"unsafe request id")],
        "state": {},
    }
    asyncio.run(RequestMetricsMiddleware(downstream)(scope, receive, send))

    start = next(message for message in sent if message["type"] == "http.response.start")
    response_id = dict(start["headers"])[b"x-request-id"].decode("ascii")
    assert len(response_id) == 32
