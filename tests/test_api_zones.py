import pytest
import numpy as np
from unittest.mock import patch, MagicMock

def test_get_mesh_success(client):
    mock_db = MagicMock()
    mock_zone = MagicMock()
    mock_zone.id = 1
    mock_zone.risk_level = 0.5
    mock_zone.created_at = None
    mock_zone.geojson = '{"type": "Polygon", "coordinates": []}'
    mock_db.query().all.return_value = [mock_zone]
    
    from app.main import app
    from app.db.session import get_db
    app.dependency_overrides[get_db] = lambda: mock_db
    
    response = client.get("/zones/mesh")
    assert response.status_code == 200
    assert response.json()["type"] == "FeatureCollection"
    assert len(response.json()["features"]) == 1
    
    app.dependency_overrides.clear()

def test_get_mesh_not_found(client):
    mock_db = MagicMock()
    mock_db.query().all.return_value = []
    
    from app.main import app
    from app.db.session import get_db
    app.dependency_overrides[get_db] = lambda: mock_db
    
    response = client.get("/zones/mesh")
    assert response.status_code == 200
    assert response.json()["metadata"]["total_zones"] == 0
    
    app.dependency_overrides.clear()

def test_generate_mesh_success(client):
    mock_db = MagicMock()
    
    # Mock hospitals/stations
    mock_station = MagicMock()
    mock_station.latitude = 12.0
    mock_station.longitude = 77.0
    mock_db.query().all.return_value = [mock_station]
    
    from app.main import app
    from app.db.session import get_db
    app.dependency_overrides[get_db] = lambda: mock_db
    
    fake_geojson = {"type": "FeatureCollection", "features": []}
    
    with patch("app.api.zones.build_risk_surface") as mock_risk:
        with patch("app.api.zones.generate_mesh") as mock_gen:
            mock_gen.return_value = []
            with patch("app.api.zones.zones_to_geojson", return_value=fake_geojson):
                response = client.post("/zones/generate")
                assert response.status_code == 200
                assert response.json()["status"] == "success"
                assert response.json()["geojson"] == fake_geojson
                    
    app.dependency_overrides.clear()

def test_get_zones_risk_surface(client):
    fake_grid = (np.array([12.0]), np.array([77.0]), np.array([[0.5]]))
    
    mock_surface = MagicMock()
    mock_surface.to_grid.return_value = fake_grid
    
    with patch("app.api.zones.build_risk_surface", return_value=mock_surface):
        response = client.get("/zones/risk-surface?resolution=10")
        assert response.status_code == 200
        data = response.json()
        assert "lats" in data
        assert "lons" in data
        assert "risk_grid" in data
        
def test_get_zones_risk_surface_bad_resolution(client):
    response = client.get("/zones/risk-surface?resolution=5")
    assert response.status_code == 400
