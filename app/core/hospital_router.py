import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.db.models import Hospital
from app.core.routing import get_osrm_eta

logger = logging.getLogger(__name__)

async def rank_hospitals(
    incident_lat: float,
    incident_lng: float,
    required_specialty: Optional[str],
    db: Session
) -> List[Dict[str, Any]]:
    """
    Ranks available hospitals based on a composite scoring function.
    
    The scoring algorithm optimizes for the following factors:
    1. ETA (Drive time): Shorter drive times yield higher base scores.
    2. Specialty Match: A critical boolean modifier. If a specific medical
       specialty is required (e.g., 'burns', 'trauma') and the hospital 
       supports it, a massive bonus is applied to ensure it ranks first 
       even if slightly further away.
    3. ER Capacity: (Stubbed) Penalizes hospitals that are full.
    
    Args:
        incident_lat (float): Latitude of the incident/victim.
        incident_lng (float): Longitude of the incident/victim.
        required_specialty (Optional[str]): The specific medical need.
        db (Session): SQLAlchemy database session.
        
    Returns:
        List[Dict[str, Any]]: A list of dictionaries containing hospital details
                              and their computed score, sorted descending by score.
    """
    # 1. Fetch all operational hospitals from the database
    hospitals = db.query(Hospital).filter(Hospital.is_24x7 == True).all()
    ranked_list = []
    
    for hospital in hospitals:
        # 2. Compute real-time ETA via OSRM
        eta_seconds = await get_osrm_eta(
            src_lat=incident_lat,
            src_lng=incident_lng,
            dst_lat=float(hospital.latitude),
            dst_lng=float(hospital.longitude)
        )
        
        # 3. Base Score Calculation
        # We start with a high base score and penalize based on drive time.
        # 1 second of drive time = 1 point penalty.
        score = 10000 - eta_seconds
        
        # 4. Specialty Bonus Application
        # If the incident requires a specific specialty, check the JSON array.
        hospital_specialties = hospital.specialties if hospital.specialties else []
        if required_specialty:
            # Case-insensitive check
            specialties_lower = [s.lower() for s in hospital_specialties]
            if required_specialty.lower() in specialties_lower:
                # Apply a massive bonus equivalent to saving ~1.3 hours of driving
                # to prioritize correct care over absolute nearest location.
                score += 5000 
                
        # 5. Capacity Checks
        if hospital.er_capacity <= 0:
            # Strictly ignore full hospitals
            continue
            
        ranked_list.append({
            "hospital_id": hospital.id,
            "name": hospital.name,
            "eta_seconds": eta_seconds,
            "specialties": hospital_specialties,
            "er_capacity": hospital.er_capacity,
            "score": score
        })
        
    # 6. Sort the list descending so the highest score is at index 0
    ranked_list.sort(key=lambda x: x["score"], reverse=True)
    
    return ranked_list
