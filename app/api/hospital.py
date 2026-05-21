from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.db.session import get_db
from app.db.models import Incident, Hospital
from app.core.hospital_router import rank_hospitals

hospital_router = APIRouter(
    prefix="/hospital",
    tags=["Hospital"]
)

@hospital_router.get("/recommend")
async def get_hospital_recommended(
    incident_id: int = Query(..., description="ID of the active incident"),
    required_specialty: Optional[str] = Query(None, description="Optional medical specialty required, e.g., 'burns', 'trauma'"),
    db: Session = Depends(get_db)
):
    """
    Given an active incident ID, this endpoint computes a real-time ranked list 
    of hospitals optimal for the victim.
    
    The ranking considers:
    - Drive time ETA (OSRM integration)
    - Medical specialty match
    - Current ER Capacity
    """
    # 1. Fetch the incident to get the victim's current coordinates
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
        
    # 2. Call the core hospital routing engine
    ranked_hospitals = await rank_hospitals(
        incident_lat=incident.latitude,
        incident_lng=incident.longitude,
        required_specialty=required_specialty,
        db=db
    )
    
    return {
        "incident_id": incident.id,
        "required_specialty": required_specialty,
        "recommendations": ranked_hospitals
    }

from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

class HospitalOverrideRequest(BaseModel):
    incident_id: Optional[int] = None
    override_reason: str
    capacity_adjustment: int = -1

@hospital_router.post("/{hospital_id}/override")
def hospital_override(
    hospital_id: int, 
    request: HospitalOverrideRequest, 
    db: Session = Depends(get_db)
):
    """
    Hospital Override Feedback Loop.
    Allows hospitals to manually signal that they are overwhelmed or divert an incoming ambulance.
    Adjusting capacity dynamically ensures `hospital_router` will exclude them from recommendations.
    """
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
        
    # Dynamically adjust capacity based on the override
    # For emergency full diversions, they might pass capacity_adjustment = -hospital.er_capacity
    new_capacity = max(0, hospital.er_capacity + request.capacity_adjustment)
    hospital.er_capacity = new_capacity
    db.commit()
    
    logger.warning(f"Hospital Override Triggered! Hospital ID {hospital_id} capacity adjusted by {request.capacity_adjustment}. New capacity: {new_capacity}. Reason: {request.override_reason}")
    
    return {
        "status": "success",
        "message": f"Hospital capacity overridden to {new_capacity}",
        "hospital_id": hospital_id
    }

@hospital_router.get("/list")
def get_hospital_list(db: Session = Depends(get_db)):
    """Fetch all registered hospitals and their basic metadata."""
    hospitals = db.query(Hospital).all()
    return {"hospitals": hospitals}