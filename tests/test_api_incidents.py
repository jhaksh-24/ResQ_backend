import pytest
from unittest.mock import patch, MagicMock
from app.db.models import Incident

def test_report_incident_success(client):
    payload = {
        "latitude": 12.9,
        "longitude": 77.6,
        "severity": 3,
        "incident_type": "cardiac"
    }
    
    # We mock the DB session's add/commit/refresh methods
    mock_db = MagicMock()
    
    # We also mock `get_db` dependency in FastAPI
    from app.main import app
    from app.db.session import get_db
    
    app.dependency_overrides[get_db] = lambda: mock_db
    
    with patch("app.api.incidents.find_best_ambulance") as mock_dispatch:
        # Mock background dispatch returning unit 5, eta 300
        mock_dispatch.return_value = (5, 300)
        
        response = client.post("/incidents/report", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        # Verify DB calls
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        
        # Verify the background task called dispatch
        mock_dispatch.assert_called_once_with(12.9, 77.6)
        
    # Clean up override
    app.dependency_overrides.clear()
