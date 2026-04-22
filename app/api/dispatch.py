from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Incident, DispatchLog, IncidentStatus
from app.core.dispatch_engine import find_best_ambulance
from app.core.fleet_state import FleetStateManager
from app.core.websocket_manager import manager

dispatch_router = APIRouter(
    prefix="/dispatch",
    tags=["Dispatch"]
)

class DispatchRequest(BaseModel):
    latitude: float
    longitude: float
    incident_type: str

@dispatch_router.post("/request")
async def create_dispatch_request(request: DispatchRequest, db: Session = Depends(get_db)):
    """Handles an incoming emergency, calculates best route, and dispatches an ambulance."""
    # 1. Ask the Brain (Dispatch Engine) for the best ambulance
    best_unit_id, best_eta = await find_best_ambulance(request.latitude, request.longitude)
    
    # 2. If no ambulances are available, fail gracefully
    if not best_unit_id:
        raise HTTPException(status_code=503, detail="No available ambulances at this time.")

    # 3. Create the Incident record in Postgres
    new_incident = Incident(
        latitude=request.latitude,
        longitude=request.longitude,
        incident_type=request.incident_type,
        status=IncidentStatus.DISPATCHED
    )
    db.add(new_incident)
    db.flush() # Flush to assign the incident ID before committing
    
    # 4. Create the Dispatch Log (Audit Trail)
    dispatch_log = DispatchLog(
        incident_id=new_incident.id,
        ambulance_id=best_unit_id,
        eta_seconds=best_eta,
        alternatives_considered=len(FleetStateManager.get_all_available()) # How many units were active
    )
    db.add(dispatch_log)
    db.commit()

    # 5. Update the hot cache (Redis) so no one else grabs this ambulance
    FleetStateManager.update_status(best_unit_id, "dispatched")
    
    # 6. Broadcast the dispatch to the live dashboard
    await manager.broadcast({
        "type": "STATUS_UPDATE",
        "unit_id": best_unit_id,
        "status": "dispatched"
    })
    
    return {
        "message": "Dispatch successful",
        "incident_id": new_incident.id,
        "assigned_unit": best_unit_id,
        "eta_seconds": best_eta
    }

@dispatch_router.get("/history")
def get_dispatch_history(db: Session = Depends(get_db)):
    """Fetch the recent dispatch audit logs from Postgres."""
    # Returns the 50 most recent dispatch logs
    logs = db.query(DispatchLog).order_by(DispatchLog.dispatched_at.desc()).limit(50).all()
    return logs
