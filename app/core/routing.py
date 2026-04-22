import httpx
import logging
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

async def get_osrm_eta(
    src_lat: float, src_lng: float, dst_lat: float, dst_lng: float
) -> int:
    """
    Calls the OSRM backend to get the drive time (ETA) in seconds.
    Returns 999999 if the route is unroutable or OSRM is down.
    """
    # Note: OSRM expects longitude,latitude
    url = f"{settings.OSRM_BASE_URL}/route/v1/driving/{src_lng},{src_lat};{dst_lng},{dst_lat}?overview=false"
    
    try:
        # 2-second timeout is critical! We can't let the dispatch loop hang waiting for routing
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") == "Ok" and "routes" in data:
                # OSRM returns duration in seconds
                return int(data["routes"][0]["duration"])
            else:
                logger.warning(f"OSRM returned non-Ok response: {data}")
                return 999999
                
    except Exception as e:
        logger.error(f"OSRM routing failed for {src_lat},{src_lng} -> {dst_lat},{dst_lng}. Error: {e}")
        # Return a massive ETA so the dispatch engine ignores this ambulance
        return 999999