import httpx
import logging
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

async def get_google_maps_eta(
    src_lat: float, src_lng: float, dst_lat: float, dst_lng: float
) -> int:
    """Fallback to Google Maps Distance Matrix API if OSRM fails."""
    if not settings.GOOGLE_MAPS_API_KEY:
        logger.warning("Google Maps fallback requested but API key is missing.")
        return 999999
        
    url = f"https://maps.googleapis.com/maps/api/distancematrix/json?destinations={dst_lat},{dst_lng}&origins={src_lat},{src_lng}&key={settings.GOOGLE_MAPS_API_KEY}"
    
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "OK" and data["rows"][0]["elements"][0]["status"] == "OK":
                duration_seconds = data["rows"][0]["elements"][0]["duration"]["value"]
                logger.info("Successfully used Google Maps fallback for routing.")
                return int(duration_seconds)
            else:
                logger.warning(f"Google Maps API returned non-OK status: {data}")
                return 999999
    except Exception as e:
        logger.error(f"Google Maps fallback failed: {e}")
        return 999999

async def get_osrm_eta(
    src_lat: float, src_lng: float, dst_lat: float, dst_lng: float
) -> int:
    """
    Calls the OSRM backend to get the drive time (ETA) in seconds.
    Falls back to Google Maps if OSRM is unroutable or down.
    """
    url = f"{settings.OSRM_BASE_URL}/route/v1/driving/{src_lng},{src_lat};{dst_lng},{dst_lat}?overview=false"
    
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            if data.get("code") == "Ok" and "routes" in data:
                return int(data["routes"][0]["duration"])
            else:
                logger.warning(f"OSRM returned non-Ok response: {data}. Falling back to Google Maps.")
                return await get_google_maps_eta(src_lat, src_lng, dst_lat, dst_lng)
                
    except Exception as e:
        logger.error(f"OSRM routing failed for {src_lat},{src_lng} -> {dst_lat},{dst_lng}. Error: {e}. Falling back to Google Maps.")
        return await get_google_maps_eta(src_lat, src_lng, dst_lat, dst_lng)