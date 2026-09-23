from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import agents, devices, discovery, enrollment, events, health, telemetry
from app.api.websocket.manager import ConnectionManager
from app.core.logging import configure_logging

configure_logging()
manager = ConnectionManager()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield


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


@app.websocket("/ws/events")
async def event_stream(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
