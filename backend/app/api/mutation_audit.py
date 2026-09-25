"""Cross-cutting audit coverage for successful authenticated human mutations."""
import logging

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.dependencies import security
from app.infrastructure.security.human_auth import audit

logger = logging.getLogger("devicemesh.audit")
_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_MACHINE_PREFIXES = ("/api/v1/agents/", "/api/v1/probes/")
_AUTH_EXEMPT = {"/api/v1/auth/login", "/api/v1/auth/refresh"}


class MutationAuditMiddleware:
    """Adds an HTTP-level audit record in addition to domain-specific audit events.

    Domain audit entries retain semantic actions such as ``service.created``. This
    middleware guarantees coverage for legacy/current human mutation endpoints
    that have not yet been migrated to an explicit domain audit call.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") not in _MUTATING_METHODS:
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if not path.startswith("/api/v1/") or path in _AUTH_EXEMPT or path.startswith(_MACHINE_PREFIXES):
            await self.app(scope, receive, send)
            return

        status_code = 500

        async def capture_status(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        await self.app(scope, receive, capture_status)
        actor = scope.get("state", {}).get("actor")
        if not actor or not 200 <= status_code < 400:
            return
        client = scope.get("client")
        source_ip = client[0] if client else None
        request_id = scope.get("state", {}).get("request_id")
        route_value = getattr(scope.get("route"), "path", None)
        route = route_value if isinstance(route_value, str) else path
        try:
            auth = security.get_human_auth_service()
            with auth.sessions.begin() as session:
                audit(
                    session,
                    str(actor),
                    "http.mutation",
                    route,
                    {"method": scope["method"], "status": status_code},
                    source_ip=source_ip,
                    request_id=request_id,
                )
        except Exception:
            # The HTTP response has already been sent; make persistence failure explicit in logs.
            logger.exception("failed to persist mutation audit", extra={"route": route, "status": status_code})
