"""
ResQ — Zones API
==================
Endpoints for the spatial engine:
  GET /zones/mesh         → GeoJSON of the current irregular zone mesh
  GET /zones/risk-surface → Risk surface as a grid (for heatmap visualization)
  POST /zones/generate    → Trigger mesh regeneration from risk surface + stations
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from geoalchemy2.functions import ST_AsGeoJSON, ST_GeomFromGeoJSON
from sqlalchemy import func

from app.db.session import get_db
from app.db.models import Zone, Station
from app.spatial.risk_surface import build_risk_surface
from app.spatial.mesh_generator import generate_mesh, zones_to_geojson

logger = logging.getLogger(__name__)

zones_router = APIRouter(
    prefix="/zones",
    tags=["Zones"]
)


@zones_router.get("/stations")
def get_dispatch_stations(db: Session = Depends(get_db)):
    """
    Returns ambulance dispatch centers (Voronoi seeds for the zone mesh).
    Used by the operator live map.
    """
    stations = db.query(Station).order_by(Station.id).all()
    return {
        "stations": [
            {
                "id": s.id,
                "name": s.name,
                "latitude": float(s.latitude),
                "longitude": float(s.longitude),
                "capacity": s.capacity,
            }
            for s in stations
        ],
        "total": len(stations),
    }


@zones_router.get("/mesh")
def get_zones_mesh(db: Session = Depends(get_db)):
    """
    Returns the current zone mesh as GeoJSON.
    Reads from the Zone table in PostGIS.
    """
    zones = db.query(
        Zone.id,
        Zone.risk_level,
        Zone.created_at,
        ST_AsGeoJSON(Zone.geom).label("geojson")
    ).all()

    if not zones:
        return {
            "type": "FeatureCollection",
            "features": [],
            "metadata": {"total_zones": 0, "message": "No zones generated yet. POST /zones/generate first."}
        }

    import json
    features = []
    for z in zones:
        features.append({
            "type": "Feature",
            "properties": {
                "zone_id": z.id,
                "risk_level": float(z.risk_level),
                "created_at": z.created_at.isoformat() if z.created_at else None,
            },
            "geometry": json.loads(z.geojson),
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {"total_zones": len(features)}
    }


@zones_router.get("/risk-surface")
def get_zones_risk_surface(resolution: int = 100):
    """
    Returns the KDE risk surface as a grid for heatmap visualization.

    Query params:
        resolution: grid resolution (default 100 → 100x100 = 10K points)
    """
    if resolution < 10 or resolution > 500:
        raise HTTPException(status_code=400, detail="Resolution must be between 10 and 500")

    try:
        surface = build_risk_surface()
        lats, lons, Z = surface.to_grid(resolution=resolution)

        return {
            "lats": lats.tolist(),
            "lons": lons.tolist(),
            "risk_grid": Z.tolist(),
            "resolution": resolution,
            "metadata": {
                "min_risk": float(Z.min()),
                "max_risk": float(Z.max()),
                "mean_risk": float(Z.mean()),
            }
        }
    except Exception as e:
        logger.error(f"Failed to build risk surface: {e}")
        raise HTTPException(status_code=500, detail=f"Risk surface computation failed: {str(e)}")


@zones_router.post("/generate")
def generate_zone_mesh(
    max_additional_vertices: int = 120,
    risk_threshold: float = 0.3,
    db: Session = Depends(get_db)
):
    """
    Trigger full mesh regeneration:
    1. Build risk surface from incident data
    2. Load station locations from DB
    3. Generate adaptive Voronoi mesh
    4. Save zones to DB (replaces existing zones)

    Query params:
        max_additional_vertices: extra vertices to inject in hotspots (default 120)
        risk_threshold: minimum risk (0-1) to trigger vertex injection (default 0.3)
    """
    try:
        # Step 1: Build risk surface
        logger.info("Building risk surface from incident data...")
        surface = build_risk_surface()

        # Step 2: Load station locations from DB
        stations = db.query(Station.latitude, Station.longitude).all()
        if not stations:
            raise HTTPException(
                status_code=400,
                detail="No stations in database. Add dispatch centers to the Station table first."
            )

        station_points = [(s.latitude, s.longitude) for s in stations]
        logger.info(f"Loaded {len(station_points)} station dispatch centers")

        # Step 3: Generate mesh
        logger.info("Generating adaptive mesh...")
        zones = generate_mesh(
            station_points=station_points,
            risk_surface=surface,
            max_additional_vertices=max_additional_vertices,
            risk_threshold=risk_threshold,
        )

        # Step 4: Clear existing zones and insert new ones
        deleted = db.query(Zone).delete()
        logger.info(f"Cleared {deleted} existing zones")

        import json
        for zone_data in zones:
            poly = zone_data["polygon"]
            geojson_str = json.dumps(poly.__geo_interface__)

            new_zone = Zone(
                geom=ST_GeomFromGeoJSON(geojson_str),
                risk_level=zone_data["risk_level"],
            )
            db.add(new_zone)

        db.commit()
        logger.info(f"Saved {len(zones)} zones to database")

        # Return the generated mesh as GeoJSON for immediate visualization
        return {
            "status": "success",
            "zones_generated": len(zones),
            "stations_used": len(station_points),
            "additional_vertices": max_additional_vertices,
            "geojson": zones_to_geojson(zones),
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Mesh generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Mesh generation failed: {str(e)}")
