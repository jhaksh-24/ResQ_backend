from fastapi import APIRouter

fleet_router = APIRouter(
    prefix="/fleet",
    tags=["Fleet"]
)

@fleet_router.get("/status")
def get_fleet_status():
    return {
        "status": "Comming soon"
    }

@fleet_router.get("/{unit_id}")
def get_fleet_unit(unit_id: int):
    return {
        "fleet_id": unit_id
    }

@fleet_router.put("/{unit_id}/location")
def update_fleet_location(unit_id: int):
    return {
        "fleet_id": unit_id,
        "Location": "Comming soon"
    }

