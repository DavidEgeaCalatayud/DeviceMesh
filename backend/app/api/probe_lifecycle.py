from __future__ import annotations

import asyncio

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.infrastructure.probe_runtime import credential_expired


class ProbeCredentialExpiryMiddleware:
    """Reject expired distributed-probe credentials before probe work is accepted."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith("/api/v1/probes/"):
            await self.app(scope, receive, send)
            return

        raw = next(
            (value for key, value in scope.get("headers", []) if key.lower() == b"authorization"),
            None,
        )
        token: str | None = None
        if raw is not None:
            try:
                authorization = raw.decode("ascii")
            except UnicodeDecodeError:
                authorization = ""
            if authorization.startswith("Bearer "):
                token = authorization.removeprefix("Bearer ").strip()

        if token and await asyncio.to_thread(credential_expired, token):
            response = JSONResponse(
                {"detail": "probe credential expired; rotate the probe token"},
                status_code=401,
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
