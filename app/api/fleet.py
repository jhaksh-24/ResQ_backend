from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.fleet_state import FleetStateManager
from app.core.websocket_manager import manager
from app.core.rebalancing import find_rebalance_destination
fleet_router = APIRouter(
    prefix="/fleet",
    tags=["Fleet"]
)

# Pydantic models for request validation
class LocationUpdate(BaseModel):
    latitude: float
    longitude: float

class StatusUpdate(BaseModel):
    status: str

@fleet_router.get("/status")
def get_fleet_status():
    """Get the status of all available ambulances."""
    available_units = FleetStateManager.get_all_available()
    return {"available_units": available_units}

@fleet_router.get("/{unit_id}")
def get_fleet_unit(unit_id: int):
    """Get real-time state of a specific ambulance."""
    state = FleetStateManager.get_unit(unit_id)
    if not state:
        raise HTTPException(status_code=404, detail="Ambulance not found in active state")
    return state

@fleet_router.put("/{unit_id}/location")
async def update_fleet_location(unit_id: int, location: LocationUpdate):
    """Update high-frequency GPS coordinates for an ambulance and broadcast to dashboard."""
    FleetStateManager.update_location(
        unit_id=unit_id,
        lat=location.latitude,
        lng=location.longitude
    )
    
    # Broadcast the new location to all connected websockets (e.g., Dispatcher Dashboard)
    await manager.broadcast({
        "type": "LOCATION_UPDATE",
        "unit_id": unit_id,
        "latitude": location.latitude,
        "longitude": location.longitude
    })
    
    return {"message": "Location updated successfully"}

@fleet_router.put("/{unit_id}/status")
async def update_fleet_status(
    unit_id: int, 
    status_update: StatusUpdate,
    db: Session = Depends(get_db)
):
    """Update the dispatch status of an ambulance and broadcast to dashboard."""
    FleetStateManager.update_status(
        unit_id=unit_id,
        status=status_update.status
    )
    
    # Broadcast the status change
    await manager.broadcast({
        "type": "STATUS_UPDATE",
        "unit_id": unit_id,
        "status": status_update.status
    })
    
    # --- Tier 3 Rebalancing Trigger ---
    # When an ambulance finishes a job and becomes 'available', 
    # immediately find the optimal zone to reposition it to.
    rebalance_cmd = None
    if status_update.status.lower() == "available":
        destination = await find_rebalance_destination(unit_id, db)
        if destination:
            # We broadcast a REBALANCE command to the crew app
            rebalance_cmd = destination
            await manager.broadcast({
                "type": "REBALANCE_COMMAND",
                "unit_id": unit_id,
                "destination": destination
            })
            
    return {
        "message": "Status updated successfully",
        "rebalance_command": rebalance_cmd
    }

@fleet_router.websocket("/ws")
async def fleet_websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for the Dispatcher Dashboard.
    Connect here to receive real-time updates when any ambulance moves or changes status.
    """
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect the dashboard to send us data, but we must keep the loop open
            # so we know when the client disconnects.
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
