from fastapi import WebSocket

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
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                # If a connection drops unexpectedly, we ignore it here; 
                # the receive loop in the endpoint will handle the disconnect.
                pass

manager = ConnectionManager()
