"""
SmartSite WebSocket Connection & Event Broadcast Manager.
Asynchronously pushes live incident alerts, camera metrics, and IoT telemetry to clients.
"""
import json
import logging
from typing import List, Dict, Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket client disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast_json(self, event_type: str, data: Dict[str, Any]):
        """Pushes structured JSON to all connected browser clients."""
        if not self.active_connections:
            return

        payload = json.dumps({"event": event_type, "data": data})
        stale = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception as e:
                stale.append(connection)

        for s in stale:
            if s in self.active_connections:
                self.active_connections.remove(s)

# Global singleton WebSocket broadcaster
ws_manager = ConnectionManager()
