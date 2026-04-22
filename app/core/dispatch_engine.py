from app.core.routing import get_osrm_eta
from app.core.fleet_state import FleetStateManager

async def find_best_ambulance(incident_lat, incident_lng):
    ambulances_available = FleetStateManager.get_all_available()

    if len(ambulances_available) == 0:
        return None, None

    best_ambulance_id = None
    best_eta = 999999

    for ambulance in ambulances_available:
        ambulance_lat = float(ambulance["latitude"])
        ambulance_lng = float(ambulance["longitude"])

        this_eta = await get_osrm_eta(ambulance_lat, ambulance_lng, incident_lat, incident_lng)
        if this_eta < best_eta:
            best_eta = this_eta
            best_ambulance_id = ambulance["unit_id"]
    
    return best_ambulance_id, best_eta