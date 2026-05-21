"""
ResQ — KDE-Based Risk Surface Generator
=========================================
Takes the incident feature CSV and generates a spatial risk surface
using Gaussian Kernel Density Estimation.

The risk surface tells the mesh generator WHERE to create denser polygons:
  - High risk → small, tight zones → more ambulance coverage
  - Low risk  → large, sparse zones → fewer resources needed

Input:  app/data/raw/bengaluru_incidents_features.csv
Output: Callable object that evaluates risk at any (lat, lon) point

Design decisions (locked in MEMORY.md):
  - KDE bandwidth: Scott's rule (adaptive)
  - Weight by severity × ward_risk_weight for incident importance
  - confidence_score=0.0 synthetic data used as structural priors
"""

import os
import logging
import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# Bengaluru bounding box — same as OSM loader
BBOX = {
    "north": 13.12,
    "south": 12.82,
    "east": 77.78,
    "west": 77.48,
}


class RiskSurface:
    """
    A spatial risk surface over Bengaluru, computed via Gaussian KDE.

    Usage:
        surface = RiskSurface.from_csv("path/to/features.csv")
        risk_at_point = surface.evaluate(12.9171, 77.6227)  # returns float 0-1
        grid = surface.to_grid(resolution=200)               # returns (lats, lons, Z)
    """

    def __init__(self, kde: gaussian_kde, lat_range: Tuple[float, float],
                 lon_range: Tuple[float, float]):
        self._kde = kde
        self._lat_range = lat_range
        self._lon_range = lon_range
        # Pre-compute the max density for normalization
        self._max_density: Optional[float] = None

    @classmethod
    def from_csv(cls, csv_path: str) -> "RiskSurface":
        """Build a risk surface from the incident features CSV."""
        logger.info(f"Loading incidents from {csv_path}")
        df = pd.read_csv(csv_path)

        # Filter to valid Bengaluru coordinates
        mask = (
            (df["latitude"] >= BBOX["south"]) & (df["latitude"] <= BBOX["north"]) &
            (df["longitude"] >= BBOX["west"]) & (df["longitude"] <= BBOX["east"])
        )
        df = df[mask].copy()
        logger.info(f"Filtered to {len(df):,} incidents within Bengaluru bbox")

        # Build weighted points: severity × ward_risk_weight
        # Higher severity + higher risk ward = stronger contribution to KDE
        weights = df["severity"].values * df["ward_risk_weight"].values

        # Stack lat/lon as 2D data for KDE (KDE expects shape [2, N])
        positions = np.vstack([df["latitude"].values, df["longitude"].values])

        # Gaussian KDE with Scott's rule (adaptive bandwidth)
        # Weighted KDE: scipy supports weights directly
        logger.info("Computing Gaussian KDE (Scott's rule, weighted)...")
        kde = gaussian_kde(positions, bw_method="scott", weights=weights)

        lat_range = (BBOX["south"], BBOX["north"])
        lon_range = (BBOX["west"], BBOX["east"])

        surface = cls(kde, lat_range, lon_range)
        logger.info("Risk surface computed successfully")
        return surface

    def evaluate(self, lat: float, lon: float) -> float:
        """
        Evaluate risk at a single point. Returns 0.0-1.0 normalized.
        """
        raw = float(self._kde(np.array([[lat], [lon]]))[0])

        if self._max_density is None:
            # Lazy-compute max density from a grid sample
            self._compute_max_density()

        return min(raw / self._max_density, 1.0)

    def evaluate_batch(self, lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
        """
        Evaluate risk at multiple points. Returns array of 0.0-1.0 normalized values.
        """
        positions = np.vstack([lats, lons])
        raw = self._kde(positions)

        if self._max_density is None:
            self._compute_max_density()

        normalized = raw / self._max_density
        return np.clip(normalized, 0.0, 1.0)

    def to_grid(self, resolution: int = 200) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Evaluate risk over a lat/lon grid.

        Returns:
            (lats_1d, lons_1d, Z_2d) where Z is shape [resolution, resolution]
            Z values are normalized 0.0-1.0
        """
        lats = np.linspace(self._lat_range[0], self._lat_range[1], resolution)
        lons = np.linspace(self._lon_range[0], self._lon_range[1], resolution)
        lon_grid, lat_grid = np.meshgrid(lons, lats)

        positions = np.vstack([lat_grid.ravel(), lon_grid.ravel()])
        Z = self._kde(positions).reshape(resolution, resolution)

        # Normalize to 0-1
        z_max = Z.max()
        if z_max > 0:
            Z = Z / z_max

        return lats, lons, Z

    def _compute_max_density(self, sample_res: int = 100):
        """Pre-compute the maximum density value for normalization."""
        lats = np.linspace(self._lat_range[0], self._lat_range[1], sample_res)
        lons = np.linspace(self._lon_range[0], self._lon_range[1], sample_res)
        lon_grid, lat_grid = np.meshgrid(lons, lats)
        positions = np.vstack([lat_grid.ravel(), lon_grid.ravel()])
        densities = self._kde(positions)
        self._max_density = float(densities.max())
        if self._max_density == 0:
            self._max_density = 1.0  # prevent division by zero


def get_data_path(filename: str) -> str:
    """Resolve path to app/data/raw/ from anywhere in the project."""
    # Walk up from this file to find app/data/raw/
    current = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current))  # app/spatial -> app -> project_root
    return os.path.join(project_root, "app", "data", "raw", filename)


def build_risk_surface() -> RiskSurface:
    """Convenience function — loads the default incident CSV and builds the surface."""
    csv_path = get_data_path("bengaluru_incidents_features.csv")
    return RiskSurface.from_csv(csv_path)
