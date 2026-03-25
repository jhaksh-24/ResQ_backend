from fastapi import APIRouter

zones_router = APIRouter(
    prefix="/zones",
    tags=["Zones"]
)

@zones_router.get("/mesh")
def get_zones_mesh():
    return {
        "message": "To be implemented"
    }

@zones_router.get("/risk-surface")
def get_zones_risk_surface():
    return {
        "message": "To be implemented"
    }
