import json

from fastapi import WebSocket


class ConnectionManager:
    """Keyed by the room's immutable database id, not its code — the code is
    user-renameable (it follows Side B's name), so it can't be used as a stable
    routing key for connections already established under the old code."""

    def __init__(self) -> None:
        self._rooms: dict[int, set[WebSocket]] = {}

    async def connect(self, room_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._rooms.setdefault(room_id, set()).add(websocket)

    def disconnect(self, room_id: int, websocket: WebSocket) -> None:
        sockets = self._rooms.get(room_id)
        if sockets is None:
            return
        sockets.discard(websocket)
        if not sockets:
            del self._rooms[room_id]

    async def send_to(self, websocket: WebSocket, message: dict) -> None:
        await websocket.send_text(json.dumps(message))

    async def broadcast(self, room_id: int, message: dict) -> None:
        sockets = self._rooms.get(room_id, set())
        payload = json.dumps(message)
        dead = []
        for ws in sockets:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            sockets.discard(ws)


manager = ConnectionManager()
