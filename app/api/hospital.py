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

@hospital_router.get("/list")
def get_hospital_list(db: Session = Depends(get_db)):
    """Fetch all registered hospitals and their basic metadata."""
    hospitals = db.query(Hospital).all()
    return {"hospitals": hospitals}