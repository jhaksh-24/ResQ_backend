import pytest
from unittest.mock import patch, MagicMock

def test_hospital_recommend_success(client):
    mock_db = MagicMock()
    # Mock Incident object
    mock_incident = MagicMock()
    mock_incident.id = 1
    mock_incident.latitude = 12.91
    mock_incident.longitude = 77.62
    mock_db.query().filter().first.return_value = mock_incident
    
    from app.main import app
    from app.db.session import get_db
    app.dependency_overrides[get_db] = lambda: mock_db
    
    fake_ranked = [
        {"hospital_id": 2, "name": "Trauma Center", "eta_seconds": 300, "score": 8000}
    ]
    
    with patch("app.api.hospital.rank_hospitals") as mock_rank:
        mock_rank.return_value = fake_ranked
        
        response = client.get("/hospital/recommend?incident_id=1&required_specialty=trauma")
        assert response.status_code == 200
        data = response.json()
        assert "recommendations" in data
        assert len(data["recommendations"]) == 1
        assert data["recommendations"][0]["hospital_id"] == 2
        mock_rank.assert_called_once_with(incident_lat=12.91, incident_lng=77.62, required_specialty="trauma", db=mock_db)
        
    app.dependency_overrides.clear()

def test_hospital_recommend_not_found(client):
    mock_db = MagicMock()
    mock_db.query().filter().first.return_value = None
    
    from app.main import app
    from app.db.session import get_db
    app.dependency_overrides[get_db] = lambda: mock_db
    
    response = client.get("/hospital/recommend?incident_id=999")
    assert response.status_code == 404
    
    app.dependency_overrides.clear()

def test_hospital_override_success(client):
    mock_db = MagicMock()
    mock_hospital = MagicMock()
    mock_hospital.id = 5
    mock_hospital.er_capacity = 10
    mock_db.query().filter().first.return_value = mock_hospital
    
    from app.main import app
    from app.db.session import get_db
    app.dependency_overrides[get_db] = lambda: mock_db
    
    payload = {
        "override_reason": "ER Full",
        "capacity_adjustment": -10
    }
    
    response = client.post("/hospital/5/override", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["hospital_id"] == 5
    
    # Capacity should drop to 0
    assert mock_hospital.er_capacity == 0
    mock_db.commit.assert_called_once()
    
    app.dependency_overrides.clear()

def test_hospital_override_not_found(client):
    mock_db = MagicMock()
    mock_db.query().filter().first.return_value = None
    
    from app.main import app
    from app.db.session import get_db
    app.dependency_overrides[get_db] = lambda: mock_db
    
    payload = {
        "override_reason": "ER Full",
        "capacity_adjustment": -10
    }
    
    response = client.post("/hospital/999/override", json=payload)
    assert response.status_code == 404
    
    app.dependency_overrides.clear()
