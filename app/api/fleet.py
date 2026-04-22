from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.fleet_state import FleetStateManager

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
def update_fleet_location(unit_id: int, location: LocationUpdate):
    """Update high-frequency GPS coordinates for an ambulance."""
    FleetStateManager.update_location(
        unit_id=unit_id,
        lat=location.latitude,
        lng=location.longitude
    )
    return {"message": "Location updated successfully"}

@fleet_router.put("/{unit_id}/status")
def update_fleet_status(unit_id: int, status_update: StatusUpdate):
    """Update the dispatch status of an ambulance."""
    FleetStateManager.update_status(
        unit_id=unit_id,
        status=status_update.status
    )
    return {"message": "Status updated successfully"}
