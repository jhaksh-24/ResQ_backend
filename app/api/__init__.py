from fastapi import APIRouter
from .dispatch import dispatch_router
from .fleet import fleet_router
from .hospital import hospital_router
from .zones import zones_router
from .incidents import incidents_router
from .mesh import mesh_router

main_router = APIRouter()

main_router.include_router(
    dispatch_router,
)

main_router.include_router(
    fleet_router
)

main_router.include_router(
    hospital_router
)

main_router.include_router(
    zones_router
)

main_router.include_router(
    incidents_router
)

main_router.include_router(
    mesh_router
)
