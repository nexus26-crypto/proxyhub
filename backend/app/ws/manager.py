import json

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: dict) -> None:
        message = json.dumps(data, default=str)
        stale = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:  # noqa: BLE001
                stale.append(connection)
        for conn in stale:
            self.disconnect(conn)


manager = ConnectionManager()
