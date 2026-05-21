import pytest
import numpy as np
from app.spatial.risk_surface import RiskSurface
from app.spatial.mesh_generator import generate_adaptive_vertices, generate_mesh, _voronoi_to_polygons
from unittest.mock import MagicMock

@pytest.fixture
def mock_surface():
    kde = MagicMock()
    kde.return_value = np.array([0.5])
    return RiskSurface(kde, (12.0, 13.0), (77.0, 78.0))

def test_risk_surface_evaluate(mock_surface):
    risk = mock_surface.evaluate(12.915, 77.625)
    assert isinstance(risk, float)
    assert risk >= 0.0

def test_generate_adaptive_vertices(mock_surface):
    station_points = [(12.0, 77.0), (12.1, 77.1), (12.2, 77.2), (12.3, 77.3)]
    
    # Mock evaluate to always return high risk
    mock_surface.evaluate = lambda lat, lon: 0.9
    
    vertices = generate_adaptive_vertices(station_points, mock_surface, max_additional=10, risk_threshold=0.5)
    
    assert len(vertices) > len(station_points)
    assert len(vertices) <= len(station_points) + 10

def test_generate_mesh_small(mock_surface):
    station_points = [(12.0, 77.0), (12.1, 77.0), (12.1, 77.1), (12.0, 77.1)]
    mock_surface.evaluate = lambda lat, lon: 0.1 # Low risk, no extra vertices
    
    zones = generate_mesh(station_points, mock_surface, max_additional_vertices=10)
    
    assert len(zones) > 0
    assert "polygon" in zones[0]
    assert "risk_level" in zones[0]

def test_risk_surface_from_csv():
    import pandas as pd
    from unittest.mock import patch
    
    fake_data = pd.DataFrame({
        "latitude": [12.91, 12.92, 12.91, 12.92],
        "longitude": [77.62, 77.63, 77.63, 77.62],
        "severity": [3, 2, 1, 1],
        "ward_risk_weight": [1.0, 1.0, 0.5, 0.5]
    })
    
    with patch("pandas.read_csv", return_value=fake_data):
        surface = RiskSurface.from_csv("fake.csv")
        assert surface is not None
        risk = surface.evaluate(12.915, 77.625)
        assert risk >= 0.0
