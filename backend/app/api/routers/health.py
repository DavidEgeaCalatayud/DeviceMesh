from fastapi import APIRouter, Depends, HTTPException
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.responses import Response

from app.api.dependencies.security import require_operator
from app.core.config import get_settings
from app.core.metrics import agents_online, incidents_open, probes_online
from app.core.version import (
    API_VERSION,
    COMPONENT_PROTOCOL_COMPATIBILITY,
    MAX_PROTOCOL_VERSION,
    MIN_PROTOCOL_VERSION,
    PROTOCOL_VERSION,
    SCHEMA_REVISION,
    SERVER_VERSION,
    SUPPORTED_PROTOCOL_VERSIONS,
)
from app.infrastructure.database import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
        if revision != SCHEMA_REVISION:
            raise HTTPException(503, "database migration required")
    except SQLAlchemyError as exc:
        raise HTTPException(503, "database unavailable") from exc
    return {"status": "ready"}


@router.get("/api/v1/system/version")
def system_version() -> dict[str, object]:
    return {
        "serverVersion": SERVER_VERSION,
        "apiVersion": API_VERSION,
        "protocolVersion": PROTOCOL_VERSION,
        "supportedProtocolVersions": list(SUPPORTED_PROTOCOL_VERSIONS),
        "minProtocolVersion": MIN_PROTOCOL_VERSION,
        "maxProtocolVersion": MAX_PROTOCOL_VERSION,
        "schemaRevision": SCHEMA_REVISION,
        "componentCompatibility": {
            component: {"protocolVersions": list(versions)}
            for component, versions in COMPONENT_PROTOCOL_COMPATIBILITY.items()
        },
    }


@router.get("/metrics", dependencies=[Depends(require_operator)], include_in_schema=False)
def metrics() -> Response:
    with engine.connect() as connection:
        agents_online.set(connection.scalar(text("SELECT count(*) FROM devices WHERE status = 'online'")) or 0)
        incidents_open.set(connection.scalar(text("SELECT count(*) FROM service_incidents WHERE state = 'open'")) or 0)
        probes_online.set(connection.scalar(text(
            "SELECT count(*) FROM synthetic_probes WHERE enabled = true "
            "AND last_seen_at > CURRENT_TIMESTAMP - (:seconds * INTERVAL '1 second')"
        ), {"seconds": get_settings().synthetic_probe_offline_after_seconds}) or 0)
    return Response(generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})
