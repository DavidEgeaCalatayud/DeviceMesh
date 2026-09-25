import asyncio

from fastapi import WebSocket

from app.core.metrics import ws_connections


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, *, accepted: bool = False) -> None:
        if not accepted:
            await websocket.accept()
        self._connections.add(websocket)
        ws_connections.set(len(self._connections))

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)
        ws_connections.set(len(self._connections))

    async def broadcast(self, payload: dict[str, object]) -> None:
        stale: list[WebSocket] = []
        for connection in tuple(self._connections):
            try:
                await asyncio.wait_for(connection.send_json(payload), timeout=2)
            except (RuntimeError, TimeoutError, OSError):
                stale.append(connection)
        for connection in stale:
            self.disconnect(connection)
