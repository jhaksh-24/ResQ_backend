import pytest
from unittest.mock import patch, MagicMock
from app.db.models import AmbulanceStatus

def test_fleet_status_success(client):
    fake_fleet = [
        {"unit_id": 1, "latitude": 12.0, "longitude": 77.0, "status": "available"}
    ]
    with patch("app.api.fleet.FleetStateManager.get_all_available", return_value=fake_fleet):
        response = client.get("/fleet/status")
        assert response.status_code == 200
        data = response.json()
        assert len(data["available_units"]) == 1
        assert data["available_units"][0]["unit_id"] == 1

def test_fleet_unit_status_success(client):
    fake_unit = {"unit_id": 5, "status": "dispatched"}
    with patch("app.api.fleet.FleetStateManager.get_unit", return_value=fake_unit):
        response = client.get("/fleet/5")
        assert response.status_code == 200
        assert response.json()["unit_id"] == 5

def test_fleet_unit_status_not_found(client):
    with patch("app.api.fleet.FleetStateManager.get_unit", return_value=None):
        response = client.get("/fleet/999")
        assert response.status_code == 404

def test_fleet_update_location(client):
    payload = {"latitude": 12.0, "longitude": 77.0}
    with patch("app.api.fleet.FleetStateManager.update_location") as mock_update:
        response = client.put("/fleet/1/location", json=payload)
        assert response.status_code == 200
        assert response.json()["message"] == "Location updated successfully"
        mock_update.assert_called_once_with(unit_id=1, lat=12.0, lng=77.0)

def test_fleet_update_status(client):
    payload = {"status": AmbulanceStatus.AVAILABLE.value}
    
    mock_db = MagicMock()
    from app.main import app
    from app.db.session import get_db
    app.dependency_overrides[get_db] = lambda: mock_db

    with patch("app.api.fleet.FleetStateManager.update_status") as mock_update:
        with patch("app.api.fleet.find_rebalance_destination") as mock_reb:
            mock_reb.return_value = None
            response = client.put("/fleet/1/status", json=payload)
            assert response.status_code == 200
            assert response.json()["message"] == "Status updated successfully"
            mock_update.assert_called_once_with(unit_id=1, status=AmbulanceStatus.AVAILABLE.value)
            
    app.dependency_overrides.clear()
