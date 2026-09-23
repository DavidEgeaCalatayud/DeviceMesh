import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import (
    agents,
    alerts,
    devices,
    discovery,
    enrollment,
    events,
    health,
    network,
    telemetry,
)
from app.api.websocket.manager import ConnectionManager
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.domain.events.models import DeviceEvent
from app.runtime import offline_device_sweeper, realtime_event_publisher

configure_logging()
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
    while True:
        event = await realtime_event_publisher.receive()
        await manager.broadcast(_event_envelope(event))


async def _sweep_offline_devices() -> None:
    settings = get_settings()
    while True:
        await asyncio.to_thread(offline_device_sweeper.sweep, datetime.now(UTC))
        await asyncio.sleep(settings.device_offline_sweep_interval_seconds)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    realtime_event_publisher.bind(asyncio.get_running_loop())
    tasks = [
        asyncio.create_task(_forward_realtime_events()),
        asyncio.create_task(_sweep_offline_devices()),
    ]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        realtime_event_publisher.unbind()


app = FastAPI(title="DeviceMesh API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(enrollment.router)
app.include_router(agents.router)
app.include_router(devices.router)
app.include_router(discovery.router)
app.include_router(events.router)
app.include_router(telemetry.router)
app.include_router(telemetry.operator_router)
app.include_router(alerts.router)
app.include_router(network.router)


@app.websocket("/ws/events")
async def event_stream(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
