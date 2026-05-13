"""In-memory WebSocket connection manager per point."""
from __future__ import annotations

from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, point_id: str, ws: WebSocket):
        await ws.accept()
        self._connections[point_id].append(ws)

    def disconnect(self, point_id: str, ws: WebSocket):
        self._connections[point_id].remove(ws)

    async def broadcast(self, point_id: str, data: dict):
        dead = []
        for ws in self._connections.get(point_id, []):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections[point_id].remove(ws)


ws_manager = ConnectionManager()
