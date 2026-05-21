import pytest
from unittest.mock import patch, MagicMock

def test_dispatch_request_success(client):
    payload = {
        "latitude": 12.91,
        "longitude": 77.62,
        "incident_type": "trauma",
        "severity": 3
    }
    
    mock_db = MagicMock()
    mock_incident = MagicMock()
    mock_incident.id = 1
    mock_db.add.return_value = None
    
    from app.main import app
    from app.db.session import get_db
    app.dependency_overrides[get_db] = lambda: mock_db
    
    with patch("app.api.dispatch.find_best_ambulance") as mock_find:
        mock_find.return_value = (10, 300)
        with patch("app.api.dispatch.FleetStateManager.get_dispatchable_units", return_value=[{"unit_id": 10}]):
            with patch("app.api.dispatch.FleetStateManager.update_status"):
                response = client.post("/dispatch/request", json=payload)
                
                assert response.status_code == 200
                data = response.json()
                assert data["message"] == "Dispatch successful"
                assert data["assigned_unit"] == 10
                assert data["eta_seconds"] == 300
                mock_find.assert_called_once_with(12.91, 77.62)
                
    app.dependency_overrides.clear()

def test_dispatch_request_no_ambulances(client):
    payload = {
        "latitude": 12.91,
        "longitude": 77.62,
        "incident_type": "trauma",
        "severity": 3
    }
    
    with patch("app.api.dispatch.find_best_ambulance") as mock_find:
        mock_find.return_value = (None, None)
        
        response = client.post("/dispatch/request", json=payload)
        
        assert response.status_code == 503
        assert "No available ambulances" in response.json()["detail"]
