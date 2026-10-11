import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies.security import human_access_gate, require_human
from app.api.mutation_audit import MutationAuditMiddleware
from app.api.probe_lifecycle import ProbeCredentialExpiryMiddleware
from app.api.routers import (
    agents,
    alerts,
    auth,
    devices,
    discovery,
    enrollment,
    events,
    health,
    network,
    nms,
    notifications,
    operational_health,
    operations,
    platform,
    probe_credentials,
    probe_runtime,
    synthetics,
    syslog,
    telemetry,
)
from app.api.websocket.manager import ConnectionManager
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.metrics import RequestMetricsMiddleware
from app.core.version import SERVER_VERSION
from app.domain.events.models import DeviceEvent
from app.runtime import (
    offline_device_sweeper,
    realtime_event_publisher,
    synthetic_probe_worker,
)
from app.worker import run_jobs

configure_logging(service_name="api")
manager = ConnectionManager()


def _event_envelope(event: DeviceEvent) -> dict[str, object]:
    return {
        "type": "device.event",
        "payload": {
            "deviceId": event.device_id,
            "name": event.name,
            "timestamp": event.timestamp.isoformat(),
            "severity": event.severity.value,
            "attributes": event.attributes,
        },
    }


async def _forward_realtime_events() -> None:
    async for event in realtime_event_publisher.events():
        await manager.broadcast(_event_envelope(event))


async def _sweep_offline_devices() -> None:
    settings = get_settings()
    while True:
        await asyncio.to_thread(offline_device_sweeper.sweep, datetime.now(UTC))
        await asyncio.sleep(settings.device_offline_sweep_interval_seconds)


async def _run_synthetic_probes() -> None:
    settings = get_settings()
    while True:
        await synthetic_probe_worker.run_due(datetime.now(UTC))
        await asyncio.sleep(settings.synthetic_probe_sweep_interval_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    realtime_event_publisher.bind(asyncio.get_running_loop())
    tasks = [
        asyncio.create_task(_forward_realtime_events()),
    ]
    if get_settings().embedded_workers:
        tasks.append(asyncio.create_task(run_jobs(asyncio.Event())))
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        realtime_event_publisher.unbind()


app = FastAPI(title="DeviceMesh API", version=SERVER_VERSION, lifespan=lifespan,
              dependencies=[Depends(human_access_gate)])
app.add_middleware(RequestMetricsMiddleware)
app.add_middleware(MutationAuditMiddleware)
app.add_middleware(ProbeCredentialExpiryMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(platform.router)
app.include_router(enrollment.router)
app.include_router(agents.router)
app.include_router(devices.router)
app.include_router(discovery.router)
app.include_router(events.router)
app.include_router(telemetry.router)
app.include_router(telemetry.operator_router)
app.include_router(alerts.router)
app.include_router(notifications.router)
app.include_router(network.router)
app.include_router(nms.router)
app.include_router(nms.operator_router)
app.include_router(operational_health.router)
app.include_router(operations.router)
app.include_router(synthetics.router)
app.include_router(syslog.router)
app.include_router(probe_credentials.router)
app.include_router(probe_runtime.router)


@app.websocket("/ws/events")
async def event_stream(websocket: WebSocket) -> None:
    settings = get_settings()
    if not settings.public_reads:
        origin = websocket.headers.get("origin")
        if origin and origin not in settings.cors_origins:
            await websocket.close(code=1008)
            return
        await websocket.accept()
        try:
            message = await asyncio.wait_for(websocket.receive_json(), timeout=5)
            principal = await asyncio.to_thread(require_human, f"Bearer {message.get('token', '')}")
            # Tokens are sent in a first frame, never in URL/query or access logs.
            websocket.state.principal = principal
        except (HTTPException, TimeoutError, ValueError, AttributeError, WebSocketDisconnect):
            await websocket.close(code=1008)
            return
    await manager.connect(websocket, accepted=not settings.public_reads)
    try:
        while True:
            await asyncio.wait_for(websocket.receive_text(), timeout=60)
            if not settings.public_reads:
                # Expiry/revocation is checked on every client heartbeat.
                await asyncio.to_thread(require_human, f"Bearer {message.get('token', '')}")
    except WebSocketDisconnect:
        pass
    except (TimeoutError, HTTPException):
        await websocket.close(code=1008)
    finally:
        manager.disconnect(websocket)
