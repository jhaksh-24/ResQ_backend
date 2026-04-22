import logging
from sqlalchemy.orm import Session
from app.db.models import Zone
from app.core.fleet_state import FleetStateManager
from app.utils.distance import haversine_distance
from geoalchemy2.functions import ST_X, ST_Y, ST_Centroid

logger = logging.getLogger(__name__)

async def find_rebalance_destination(unit_id: int, db: Session):
    """
    Tier 3 Rebalancing: Passive Post-Handoff.
    Finds the optimal zone for an ambulance to relocate to after dropping off a patient.
    
    Algorithm:
    1. Fetch all zones and compute their centroid (center point).
    2. Identify the distance from each zone to the nearest AVAILABLE ambulance.
    3. Calculate 'Coverage Gap' = Zone Risk Level * Distance to Nearest Ambulance.
    4. Send the newly available unit to the zone with the highest Coverage Gap.
    """
    # 1. Get all available fleet EXCEPT this unit
    all_available = FleetStateManager.get_all_available()
    other_ambulances = [a for a in all_available if a.get("unit_id") != unit_id]
    
    # 2. Get all zones with their centroids using PostGIS functions
    # ST_Y is latitude, ST_X is longitude
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
        logger.warning("No zones found in database for rebalancing.")
        return None
        
    best_zone = None
    highest_coverage_gap = -1
    
    for zone in zones:
        # 3. Find current distance to nearest ambulance for this zone
        nearest_amb_dist = 999999.0
        
        for amb in other_ambulances:
            amb_lat = float(amb["latitude"])
            amb_lng = float(amb["longitude"])
            # Fast Haversine straight-line approximation
            dist = haversine_distance(amb_lat, amb_lng, zone.lat, zone.lng)
            if dist < nearest_amb_dist:
                nearest_amb_dist = dist
                
        # 4. Calculate Coverage Gap
        # If there are no other ambulances, nearest_amb_dist is massive, 
        # so it just routes to the highest risk zone globally.
        coverage_gap = zone.risk_level * nearest_amb_dist
        
        if coverage_gap > highest_coverage_gap:
            highest_coverage_gap = coverage_gap
            best_zone = zone
            
    if best_zone:
        logger.info(f"Rebalancing Unit {unit_id} to Zone {best_zone.id} (Coverage Gap: {highest_coverage_gap})")
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
