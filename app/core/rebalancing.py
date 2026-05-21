from sqlalchemy.orm import Session
from app.db.models import Zone
from app.core.fleet_state import FleetStateManager
from app.utils.distance import haversine_distance
from geoalchemy2.functions import ST_X, ST_Y, ST_Centroid
from app.core.logger import get_logger, log_event
import logging

logger = get_logger(__name__)

from app.core.routing import get_osrm_eta

async def find_rebalance_destination(unit_id: int, db: Session):
    """
    Tier 3 Rebalancing: Passive Post-Handoff.
    Finds the optimal zone for an ambulance to relocate to after dropping off a patient.
    
    Architecture (Two-Pass Optimization):
    1. Pass 1 (Fast): Use Haversine to find the 5 most 'vulnerable' zones city-wide.
    2. Pass 2 (Accurate): Use OSRM to find actual drive time to those 5 zones.
    3. Decision: Optimize for maximum vulnerability reduction per minute of drive time.
    """
    # Get the state of the ambulance we are trying to rebalance
    this_amb = FleetStateManager.get_unit(unit_id)
    if not this_amb:
        return None
        
    this_lat = float(this_amb["latitude"])
    this_lng = float(this_amb["longitude"])

    all_available = FleetStateManager.get_all_available()
    other_ambulances = [a for a in all_available if a.get("unit_id") != unit_id]
    
    try:
        zones = db.query(
            Zone.id,
            Zone.risk_level,
            ST_Y(ST_Centroid(Zone.geom)).label("lat"),
            ST_X(ST_Centroid(Zone.geom)).label("lng")
        ).all()
    except Exception as e:
        logger.error(f"Failed to query zones for rebalancing: {e}")
        return None
    
    if not zones:
        return None
        
    # --- PASS 1: Haversine Pre-Filter ---
    zone_vulnerabilities = []
    
    for zone in zones:
        nearest_amb_dist = 999999.0
        for amb in other_ambulances:
            dist = haversine_distance(float(amb["latitude"]), float(amb["longitude"]), zone.lat, zone.lng)
            if dist < nearest_amb_dist:
                nearest_amb_dist = dist
                
        vulnerability = zone.risk_level * nearest_amb_dist
        zone_vulnerabilities.append({
            "zone": zone,
            "vulnerability": vulnerability
        })
        
    # Sort by vulnerability and take the Top 5
    zone_vulnerabilities.sort(key=lambda x: x["vulnerability"], reverse=True)
    top_candidates = zone_vulnerabilities[:5]
    
    # --- PASS 2: OSRM Drive Time Check ---
    best_zone = None
    best_final_score = -1
    
    for candidate in top_candidates:
        zone = candidate["zone"]
        vulnerability = candidate["vulnerability"]
        
        # How long will it take OUR ambulance to get there?
        eta_seconds = await get_osrm_eta(this_lat, this_lng, zone.lat, zone.lng)
        
        if eta_seconds >= 999999 or eta_seconds == 0:
            continue # Skip unreachable zones
            
        # Optimization Function: Vulnerability mitigated per minute of driving
        # We want to solve high vulnerability without driving across the entire city.
        eta_minutes = eta_seconds / 60.0
        final_score = vulnerability / eta_minutes
        
        if final_score > best_final_score:
            best_final_score = final_score
            best_zone = zone
            
    if best_zone:
        logger.info(f"Rebalancing Unit {unit_id} to Zone {best_zone.id} (Score: {best_final_score})")
        return {
            "target_zone_id": best_zone.id,
            "target_lat": best_zone.lat,
            "target_lng": best_zone.lng
        }
        
    return None

import asyncio
from app.db.session import SessionLocal

async def run_tier_2_rebalancing():
    """
    Tier 2 Rebalancing: Scheduled Global Sweep.
    Runs periodically (e.g., every 5 minutes) to evaluate the entire idle fleet
    against global risk surfaces.
    """
    logger.info("Starting Tier 2 Global Rebalancing Sweep...")
    
    # We create a new DB session for the background task
    db = SessionLocal()
    try:
        available_units = FleetStateManager.get_all_available()
        logger.info(f"Tier 2 Sweep: Found {len(available_units)} available units to evaluate.")
        
        # For now, this is a hook. The full Hungarian algorithm for global 
        # multi-unit optimization would go here to reassign multiple units at once.
    except Exception as e:
        logger.error(f"Tier 2 Rebalancing failed: {e}")
    finally:
        db.close()

async def rebalancing_task_loop():
    """Infinite loop for the background task."""
    while True:
        await asyncio.sleep(300) # Run every 5 minutes (300 seconds)
        try:
            await run_tier_2_rebalancing()
        except Exception as e:
            logger.error(f"Error in Tier 2 rebalancing loop: {e}")
