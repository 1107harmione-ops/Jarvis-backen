import asyncio
import time
from typing import Optional
from fastapi import WebSocket
from backend.core.config import get_settings
from backend.core.logging import log_ws_event


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.user_connections: dict[str, set[str]] = {}  # user_id → set of conn_ids
        self.connection_info: dict[str, dict] = {}  # conn_id → metadata
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, client_id: str, user_id: Optional[str] = None) -> str:
        await websocket.accept()
        async with self._lock:
            self.active_connections[client_id] = websocket
            if user_id:
                if user_id not in self.user_connections:
                    self.user_connections[user_id] = set()
                self.user_connections[user_id].add(client_id)
            self.connection_info[client_id] = {
                "connected_at": time.time(),
                "user_id": user_id,
                "client_host": websocket.client.host if websocket.client else "unknown",
                "last_activity": time.time(),
            }
        log_ws_event("connect", client_id, user_id=user_id)
        return client_id

    async def disconnect(self, client_id: str):
        async with self._lock:
            ws = self.active_connections.pop(client_id, None)
            info = self.connection_info.pop(client_id, None)
            if info and info.get("user_id"):
                user_id = info["user_id"]
                if user_id in self.user_connections:
                    self.user_connections[user_id].discard(client_id)
                    if not self.user_connections[user_id]:
                        del self.user_connections[user_id]
        if ws:
            try:
                await ws.close()
            except Exception:
                pass
        log_ws_event("disconnect", client_id)

    async def send_message(self, client_id: str, message: dict) -> bool:
        ws = self.active_connections.get(client_id)
        if ws is None:
            return False
        try:
            await ws.send_json(message)
            if client_id in self.connection_info:
                self.connection_info[client_id]["last_activity"] = time.time()
            return True
        except Exception:
            await self.disconnect(client_id)
            return False

    async def send_to_user(self, user_id: str, message: dict):
        conn_ids = self.user_connections.get(user_id, set()).copy()
        for cid in conn_ids:
            await self.send_message(cid, message)

    async def broadcast(self, message: dict):
        conn_ids = list(self.active_connections.keys())
        for cid in conn_ids:
            await self.send_message(cid, message)

    async def get_connection_count(self) -> int:
        return len(self.active_connections)

    async def get_user_connections(self, user_id: str) -> int:
        return len(self.user_connections.get(user_id, set()))

    async def heartbeat_check(self):
        """Periodically check connections and remove stale ones."""
        settings = get_settings()
        while True:
            await asyncio.sleep(settings.ws_heartbeat_interval)
            now = time.time()
            stale = []
            async with self._lock:
                for cid, info in self.connection_info.items():
                    if now - info["last_activity"] > settings.ws_max_idle_time:
                        stale.append(cid)
            for cid in stale:
                await self.disconnect(cid)
                log_ws_event("stale_timeout", cid)


# Global instance
_manager: Optional[ConnectionManager] = None


def get_manager() -> ConnectionManager:
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager
