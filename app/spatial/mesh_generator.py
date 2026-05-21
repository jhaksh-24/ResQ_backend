"""
ResQ — Irregular Adaptive Mesh Generator
==========================================
The core spatial innovation of ResQ.

Takes:
  1. A risk surface (from risk_surface.py)
  2. Station locations (dispatch centers = Voronoi seeds)

Produces:
  Irregular polygons (zones) where:
  - High-risk areas → denser, smaller polygons
  - Low-risk areas  → sparser, larger polygons

Algorithm:
  1. Load station locations (dispatch centers) as primary vertices
  2. Evaluate risk surface at each station
  3. In high-risk regions, inject additional vertices proportional to risk density
     (this is where the "probability topological curve" drives mesh density)
  4. Run Voronoi tessellation over all vertices
  5. Clip to Bengaluru bounding box
  6. Output Shapely Polygon objects ready for PostGIS insertion

Design decisions (from MEMORY.md):
  - Vertices = station dispatch centers
  - Risk surface drives vertex density (adaptive)
  - SRID=4326 for all geometry
"""

import os
import logging
import numpy as np
from scipy.spatial import Voronoi
from shapely.geometry import Polygon, MultiPoint, box
from shapely.ops import unary_union
from typing import List, Tuple, Dict, Optional

from app.spatial.risk_surface import RiskSurface, BBOX

logger = logging.getLogger(__name__)

# Bengaluru clip box as Shapely geometry
BENGALURU_BOUNDS = box(BBOX["west"], BBOX["south"], BBOX["east"], BBOX["north"])


def _voronoi_to_polygons(
    vor: Voronoi, clip_box: Polygon
) -> List[Tuple[int, Polygon]]:
    """
    Convert a scipy Voronoi diagram into clipped Shapely polygons.

    Returns list of (point_index, polygon) tuples.
    Infinite regions are handled by extending rays to the bounding box.
    """
    polygons = []
    center = vor.points.mean(axis=0)

    for point_idx, region_idx in enumerate(vor.point_region):
        region = vor.regions[region_idx]
        if not region or -1 in region:
            # Infinite region — build from finite vertices + extended rays
            poly = _build_infinite_region(vor, point_idx, region_idx, clip_box, center)
            if poly is not None and poly.is_valid and not poly.is_empty:
                clipped = poly.intersection(clip_box)
                if not clipped.is_empty:
                    if clipped.geom_type == "Polygon":
                        polygons.append((point_idx, clipped))
                    elif clipped.geom_type == "MultiPolygon":
                        # Take the largest piece
                        largest = max(clipped.geoms, key=lambda g: g.area)
                        polygons.append((point_idx, largest))
        else:
            # Finite region
            verts = [vor.vertices[i] for i in region]
            poly = Polygon(verts)
            if poly.is_valid and not poly.is_empty:
                clipped = poly.intersection(clip_box)
                if not clipped.is_empty:
                    if clipped.geom_type == "Polygon":
                        polygons.append((point_idx, clipped))
                    elif clipped.geom_type == "MultiPolygon":
                        largest = max(clipped.geoms, key=lambda g: g.area)
                        polygons.append((point_idx, largest))

    return polygons


def _build_infinite_region(
    vor: Voronoi, point_idx: int, region_idx: int,
    clip_box: Polygon, center: np.ndarray
) -> Optional[Polygon]:
    """Build a polygon for an infinite Voronoi region by extending rays far out."""
    region = vor.regions[region_idx]
    if not region:
        return None

    # Collect finite vertices
    finite_verts = []
    for idx in region:
        if idx >= 0:
            finite_verts.append(vor.vertices[idx])

    if len(finite_verts) < 1:
        return None

    # Find ridges that belong to this point
    point = vor.points[point_idx]
    far_points = list(finite_verts)

    for ridge_points, ridge_verts in zip(vor.ridge_points, vor.ridge_vertices):
        if point_idx not in ridge_points:
            continue
        if -1 not in ridge_verts:
            continue

        # One vertex is at infinity — extend the other
        finite_vert_idx = [v for v in ridge_verts if v >= 0]
        if not finite_vert_idx:
            continue

        finite_vert = vor.vertices[finite_vert_idx[0]]

        # Direction: perpendicular to the ridge, pointing away from center
        other_point_idx = ridge_points[0] if ridge_points[1] == point_idx else ridge_points[1]
        midpoint = 0.5 * (vor.points[point_idx] + vor.points[other_point_idx])
        direction = midpoint - center
        norm = np.linalg.norm(direction)
        if norm < 1e-10:
            continue
        direction = direction / norm

        # Extend far enough to cover the bounding box
        far_point = finite_vert + direction * 2.0  # 2 degrees ~ 200km, more than enough
        far_points.append(far_point)

    if len(far_points) < 3:
        return None

    # Sort points by angle around centroid to form a valid polygon
    centroid = np.mean(far_points, axis=0)
    angles = [np.arctan2(p[1] - centroid[1], p[0] - centroid[0]) for p in far_points]
    sorted_points = [p for _, p in sorted(zip(angles, far_points))]

    try:
        poly = Polygon(sorted_points)
        if not poly.is_valid:
            poly = poly.buffer(0)  # fix self-intersections
        return poly
    except Exception:
        return None


def generate_adaptive_vertices(
    station_points: List[Tuple[float, float]],
    risk_surface: RiskSurface,
    max_additional: int = 120,
    risk_threshold: float = 0.3
) -> np.ndarray:
    """
    Generate additional vertices in high-risk zones to increase mesh density.

    The risk surface from KDE drives where we place extra Voronoi seeds:
    - Areas with risk > threshold get additional vertices
    - Number of added points proportional to risk intensity
    - This creates the "probability topological curve" effect from the synopsis

    Args:
        station_points: (lat, lon) of dispatch centers — primary vertices
        risk_surface: KDE risk surface object
        max_additional: maximum extra vertices to add across the city
        risk_threshold: minimum risk level (0-1) to trigger vertex injection

    Returns:
        np.ndarray of shape [N, 2] with all vertices (lon, lat) — Voronoi expects (x, y)
    """
    # Start with station locations (primary vertices)
    # Voronoi expects (x, y) = (lon, lat)
    all_points = [(lon, lat) for lat, lon in station_points]

    # Sample the risk surface on a grid to find high-risk zones
    grid_res = 50
    lats = np.linspace(BBOX["south"], BBOX["north"], grid_res)
    lons = np.linspace(BBOX["west"], BBOX["east"], grid_res)

    # Evaluate risk at each grid cell
    risk_scores = []
    for lat in lats:
        for lon in lons:
            risk = risk_surface.evaluate(lat, lon)
            if risk >= risk_threshold:
                risk_scores.append((lat, lon, risk))

    if not risk_scores:
        logger.warning("No high-risk zones found above threshold — using stations only")
        return np.array(all_points)

    # Distribute additional vertices proportional to risk scores
    total_risk = sum(r for _, _, r in risk_scores)
    additional_added = 0

    for lat, lon, risk in risk_scores:
        if additional_added >= max_additional:
            break

        # Number of extra points for this cell proportional to its risk share
        n_extra = max(1, int(round(risk / total_risk * max_additional)))
        n_extra = min(n_extra, max_additional - additional_added)

        # Place points with small random offset around the grid cell
        cell_size_lat = (BBOX["north"] - BBOX["south"]) / grid_res
        cell_size_lon = (BBOX["east"] - BBOX["west"]) / grid_res

        for _ in range(n_extra):
            jitter_lat = lat + np.random.uniform(-cell_size_lat / 2, cell_size_lat / 2)
            jitter_lon = lon + np.random.uniform(-cell_size_lon / 2, cell_size_lon / 2)
            all_points.append((jitter_lon, jitter_lat))
            additional_added += 1

    logger.info(
        f"Mesh vertices: {len(station_points)} stations + "
        f"{additional_added} risk-injected = {len(all_points)} total"
    )
    return np.array(all_points)


def generate_mesh(
    station_points: List[Tuple[float, float]],
    risk_surface: RiskSurface,
    max_additional_vertices: int = 120,
    risk_threshold: float = 0.3,
) -> List[Dict]:
    """
    Generate the irregular adaptive mesh.

    Args:
        station_points: list of (lat, lon) dispatch center locations
        risk_surface: KDE risk surface object
        max_additional_vertices: how many extra vertices to inject in hot zones
        risk_threshold: risk level (0-1) above which to inject extra vertices

    Returns:
        List of dicts, each with:
          - "polygon": Shapely Polygon (SRID=4326, coordinates in lon/lat)
          - "risk_level": float 0-1 (average risk across the polygon)
          - "vertex_lat": float (the Voronoi seed latitude)
          - "vertex_lon": float (the Voronoi seed longitude)
    """
    np.random.seed(42)  # reproducible mesh

    # Step 1: Generate all vertices (stations + risk-injected)
    all_vertices = generate_adaptive_vertices(
        station_points, risk_surface,
        max_additional=max_additional_vertices,
        risk_threshold=risk_threshold
    )

    if len(all_vertices) < 4:
        raise ValueError(f"Need at least 4 vertices for Voronoi, got {len(all_vertices)}")

    # Step 2: Run Voronoi tessellation
    logger.info(f"Running Voronoi tessellation over {len(all_vertices)} vertices...")
    vor = Voronoi(all_vertices)

    # Step 3: Convert to clipped Shapely polygons
    raw_polygons = _voronoi_to_polygons(vor, BENGALURU_BOUNDS)
    logger.info(f"Generated {len(raw_polygons)} valid zones (clipped to Bengaluru bbox)")

    # Step 4: Compute risk level for each zone (centroid-based)
    zones = []
    for point_idx, polygon in raw_polygons:
        centroid = polygon.centroid
        risk_level = risk_surface.evaluate(centroid.y, centroid.x)  # lat=y, lon=x

        # Get the seed vertex location
        vertex_lon, vertex_lat = all_vertices[point_idx]

        zones.append({
            "polygon": polygon,
            "risk_level": float(risk_level),
            "vertex_lat": float(vertex_lat),
            "vertex_lon": float(vertex_lon),
        })

    # Sort by risk level descending so high-risk zones are at the top
    zones.sort(key=lambda z: z["risk_level"], reverse=True)

    logger.info(
        f"Mesh complete: {len(zones)} zones, "
        f"risk range [{zones[-1]['risk_level']:.3f}, {zones[0]['risk_level']:.3f}]"
    )
    return zones


def zones_to_geojson(zones: List[Dict]) -> Dict:
    """Convert zone list to GeoJSON FeatureCollection for the API."""
    features = []
    for i, zone in enumerate(zones):
        poly = zone["polygon"]
        # Shapely's __geo_interface__ gives GeoJSON-compatible geometry
        features.append({
            "type": "Feature",
            "properties": {
                "zone_index": i,
                "risk_level": round(zone["risk_level"], 4),
                "vertex_lat": zone["vertex_lat"],
                "vertex_lon": zone["vertex_lon"],
                "area_sq_deg": round(poly.area, 6),
            },
            "geometry": poly.__geo_interface__,
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "total_zones": len(zones),
            "bbox": [BBOX["west"], BBOX["south"], BBOX["east"], BBOX["north"]],
        }
    }
