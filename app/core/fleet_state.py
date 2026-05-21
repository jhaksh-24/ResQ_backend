import redis
import warnings
from typing import Dict, List, Optional
from datetime import datetime, timezone
from app.config import get_settings

# Suppress redis-py deprecation warning for hmset — we use it for Redis 3.x compat
warnings.filterwarnings("ignore", message=r"Redis\.hmset", category=DeprecationWarning)

settings = get_settings()

# Initialize Redis client. decode_responses=True ensures we get strings back instead of bytes.
redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

class FleetStateManager:
    """Manages the real-time state of the ambulance fleet using Redis."""
    
    @staticmethod
    def _get_key(unit_id: int) -> str:
        return f"ambulance:{unit_id}"

    @staticmethod
    def update_location(unit_id: int, lat: float, lng: float) -> None:
        """Updates the GPS coordinates of an ambulance."""
        key = FleetStateManager._get_key(unit_id)
        # Enforce type casting to prevent corrupted fleet states
        lat_f, lng_f = float(lat), float(lng)
        # Use hmset for Redis 3.x compatibility (hset mapping= requires Redis 4.0+)
        redis_client.hmset(key, {
            "latitude": lat_f,
            "longitude": lng_f,
            "updated_at": datetime.now(timezone.utc).isoformat()
        })

    @staticmethod
    def update_status(unit_id: int, status: str) -> None:
        """Updates the current status of an ambulance (e.g., 'available', 'dispatched')."""
        key = FleetStateManager._get_key(unit_id)
        # Use hmset for Redis 3.x compatibility (hset mapping= requires Redis 4.0+)
        redis_client.hmset(key, {
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat()
        })

    @staticmethod
    def get_unit(unit_id: int) -> Optional[Dict[str, str]]:
        """Retrieves the full real-time state of a specific ambulance."""
        key = FleetStateManager._get_key(unit_id)
        data = redis_client.hgetall(key)
        if not data:
            return None
        return data

    @staticmethod
    def get_all_available() -> List[Dict[str, str]]:
        """Finds all ambulances currently marked as 'available'."""
        available_units = []
        # scan_iter is safer than keys() because it won't block Redis if there are millions of keys
        all_keys = redis_client.scan_iter(match="ambulance:*")
        
        for key in all_keys:
            state = redis_client.hgetall(key)
            if state.get("status") == "available":
                # Inject the unit_id back into the dictionary for convenience
                state["unit_id"] = int(key.split(":")[1])
                available_units.append(state)
                
        return available_units

    @staticmethod
    def get_dispatchable_units() -> List[Dict[str, str]]:
        """
        Finds all ambulances that can be dispatched immediately.
        This includes 'available' and 'returning' (free-agent reassignment).
        """
        dispatchable_units = []
        all_keys = redis_client.scan_iter(match="ambulance:*")
        
        for key in all_keys:
            state = redis_client.hgetall(key)
            if state.get("status") in ["available", "returning"]:
                state["unit_id"] = int(key.split(":")[1])
                dispatchable_units.append(state)
                
        return dispatchable_units