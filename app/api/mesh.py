"""
ResQ — Dispatch Center & Mesh API
====================================
Frontend-facing endpoints for the Operator Dashboard map layer.

  GET /api/dispatch-centers  → Station nodes with risk levels & live fleet counts
  GET /api/mesh              → KNN adjacency links between stations for mesh overlay

These endpoints bridge the real database/Redis state with the Leaflet
map on the operator UI. The risk classification comes from the KDE
risk surface (not a hardcoded grid), and fleet counts are pulled live
from the Redis hot-state layer.
"""

import logging
from typing import List, Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.db.models import Station, Ambulance, AmbulanceStatus
from app.core.fleet_state import FleetStateManager, redis_client
from app.spatial.risk_surface import build_risk_surface, BBOX

logger = logging.getLogger(__name__)

mesh_router = APIRouter(
    prefix="/api",
    tags=["Mesh & Dispatch Centers"]
)

# ─────────────────────────────────────────────────────────────────────────────
# Lazy-loaded risk surface singleton (expensive to compute, cache it)
# ─────────────────────────────────────────────────────────────────────────────
_risk_surface_cache = None


def _get_risk_surface():
    """Load the KDE risk surface once and cache it for the process lifetime."""
    global _risk_surface_cache
    if _risk_surface_cache is None:
        try:
            logger.info("Loading KDE risk surface for dispatch center classification...")
            _risk_surface_cache = build_risk_surface()
            logger.info("Risk surface loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load risk surface: {e}")
            return None
    return _risk_surface_cache


def _classify_risk(risk_score: float) -> str:
    """
    Classify a 0.0–1.0 normalized risk score into HIGH / MEDIUM / LOW.
    Thresholds calibrated to the KDE output distribution:
      >= 0.6  → HIGH   (dense accident zones — ORR, Silk Board, etc.)
      >= 0.3  → MEDIUM (moderate traffic corridors)
      <  0.3  → LOW    (residential / outskirts)
    """
    if risk_score >= 0.6:
        return "HIGH"
    elif risk_score >= 0.3:
        return "MEDIUM"
    return "LOW"


def _get_active_fleet_count(station_id: int, db: Session) -> int:
    """
    Count ambulances assigned to this station that are currently
    active (not offline) in the Redis hot-state layer.
    """
    ambulances = db.query(Ambulance.id).filter(
        Ambulance.station_id == station_id
    ).all()

    active = 0
    for (amb_id,) in ambulances:
        state = FleetStateManager.get_unit(amb_id)
        if state and state.get("status") not in (None, "offline"):
            active += 1
    return active


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/dispatch-centers
# ─────────────────────────────────────────────────────────────────────────────
@mesh_router.get("/dispatch-centers")
def get_dispatch_centers(db: Session = Depends(get_db)):
    """
    Returns all dispatch centers (stations) with:
    - Live risk classification from the KDE risk surface
    - Real capacity from the DB
    - Live active fleet count from Redis

    Response format matches the frontend Leaflet overlay contract.
    """
    stations = db.query(Station).all()
    if not stations:
        return {"centers": []}

    surface = _get_risk_surface()

    centers = []
    for station in stations:
        # Evaluate risk at this station's exact coordinates
        if surface:
            risk_score = surface.evaluate(station.latitude, station.longitude)
        else:
            risk_score = 0.5  # fallback if risk surface fails to load

        risk_level = _classify_risk(risk_score)
        active_count = _get_active_fleet_count(station.id, db)

        centers.append({
            "id": f"DC-{station.id}",
            "name": station.name,
            "lat": round(station.latitude, 4),
            "lng": round(station.longitude, 4),
            "riskLevel": risk_level,
            "riskScore": round(risk_score, 4),
            "capacity": station.capacity,
            "activeFleetCount": active_count,
        })

    # Sort by risk score descending so high-risk centers are listed first
    centers.sort(key=lambda c: c["riskScore"], reverse=True)

    logger.info(
        f"Returning {len(centers)} dispatch centers "
        f"(HIGH={sum(1 for c in centers if c['riskLevel']=='HIGH')}, "
        f"MEDIUM={sum(1 for c in centers if c['riskLevel']=='MEDIUM')}, "
        f"LOW={sum(1 for c in centers if c['riskLevel']=='LOW')})"
    )

    return {"centers": centers}


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/mesh
# ─────────────────────────────────────────────────────────────────────────────
@mesh_router.get("/mesh")
def get_mesh(
    k: int = Query(default=3, ge=1, le=6, description="Number of nearest neighbors per node"),
    db: Session = Depends(get_db)
):
    """
    Computes the irregular mesh link lines between adjacent dispatch centers
    using K-Nearest Neighbors spatial clustering.

    Each station is connected to its K closest neighbors (default K=3).
    Duplicate/reverse links are deduplicated.

    Higher K = denser mesh. K=2 is sparse, K=3 is balanced, K=4+ is dense.
    """
    stations = db.query(Station).all()
    if not stations:
        return {"links": []}

    surface = _get_risk_surface()

    # Build coordinate list
    coords = []
    for s in stations:
        risk_score = surface.evaluate(s.latitude, s.longitude) if surface else 0.5
        coords.append({
            "id": s.id,
            "lat": s.latitude,
            "lng": s.longitude,
            "risk": risk_score,
        })

    links = []
    visited = set()

    for i, c1 in enumerate(coords):
        # Compute squared distances to all other stations
        distances = []
        for j, c2 in enumerate(coords):
            if i == j:
                continue
            dist_sq = (c1["lat"] - c2["lat"]) ** 2 + (c1["lng"] - c2["lng"]) ** 2
            distances.append((j, dist_sq))

        distances.sort(key=lambda x: x[1])

        # Connect to K nearest neighbors
        for n in range(min(k, len(distances))):
            j = distances[n][0]
            c2 = coords[j]

            # Deduplicate: only add if this pair hasn't been seen
            pair_key = (min(c1["id"], c2["id"]), max(c1["id"], c2["id"]))
            if pair_key not in visited:
                # Classify link risk as the higher of the two endpoints
                link_risk = max(c1["risk"], c2["risk"])
                links.append({
                    "from": {"lat": round(c1["lat"], 4), "lng": round(c1["lng"], 4)},
                    "to": {"lat": round(c2["lat"], 4), "lng": round(c2["lng"], 4)},
                    "riskLevel": _classify_risk(link_risk),
                })
                visited.add(pair_key)

    logger.info(f"Mesh computed: {len(links)} links across {len(coords)} stations (K={k})")

    return {"links": links}
