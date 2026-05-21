from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages active WebSocket connections for real-time fleet tracking."""
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Sends a JSON message to all connected clients (e.g., dispatcher dashboard)."""
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"WebSocket send failed, removing dead connection: {e}")
                dead_connections.append(connection)
        # Auto-clean dead connections so they don't accumulate
        for dead in dead_connections:
            self.disconnect(dead)

manager = ConnectionManager()
