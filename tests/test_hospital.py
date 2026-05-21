import pytest
from app.core.hospital_router import rank_hospitals
from unittest.mock import patch, MagicMock

class FakeHospital:
    def __init__(self, id, name, lat, lng, capacity, specialties):
        self.id = id
        self.name = name
        self.latitude = lat
        self.longitude = lng
        self.er_capacity = capacity
        self.specialties = specialties
        self.is_24x7 = True

@pytest.mark.asyncio
async def test_find_nearest_hospital_capacity_exhausted():
    hospitals = [
        FakeHospital(1, "Full Hospital", 12.0, 77.0, 0, ["trauma"])
    ]
    with patch("app.core.hospital_router.get_osrm_eta", return_value=100):
        mock_db = MagicMock()
        mock_db.query().filter().all.return_value = hospitals
        
        ranked = await rank_hospitals(12.0, 77.0, "trauma", mock_db)
        assert len(ranked) == 0

@pytest.mark.asyncio
async def test_find_nearest_hospital_specialty_mismatch():
    hospitals = [
        FakeHospital(1, "Cardiac Only", 12.0, 77.0, 10, ["cardiac"]),
        FakeHospital(2, "Trauma Center", 12.1, 77.1, 10, ["trauma"])
    ]
    async def mock_osrm(src_lat, src_lng, dst_lat, dst_lng):
        if dst_lat == 12.0:
            return 100
        return 300
        
    with patch("app.core.hospital_router.get_osrm_eta", side_effect=mock_osrm):
        mock_db = MagicMock()
        mock_db.query().filter().all.return_value = hospitals
        
        ranked = await rank_hospitals(12.0, 77.0, "trauma", mock_db)
        assert len(ranked) == 2
        assert ranked[0]["hospital_id"] == 2 # Specialty bonus should make it #1
        assert ranked[0]["eta_seconds"] == 300

@pytest.mark.asyncio
async def test_find_nearest_hospital_no_hospitals():
    mock_db = MagicMock()
    mock_db.query().filter().all.return_value = []
    
    ranked = await rank_hospitals(12.0, 77.0, "trauma", mock_db)
    assert len(ranked) == 0

@pytest.mark.asyncio
async def test_find_nearest_hospital_success():
    hospitals = [
        FakeHospital(1, "H1", 12.0, 77.0, 5, ["burns", "trauma"]),
        FakeHospital(2, "H2", 12.1, 77.1, 5, ["trauma"])
    ]
    async def mock_osrm(src_lat, src_lng, dst_lat, dst_lng):
        if dst_lat == 12.0:
            return 500
        return 200
        
    with patch("app.core.hospital_router.get_osrm_eta", side_effect=mock_osrm):
        mock_db = MagicMock()
        mock_db.query().filter().all.return_value = hospitals
        
        ranked = await rank_hospitals(12.0, 77.0, "trauma", mock_db)
        assert len(ranked) == 2
        assert ranked[0]["hospital_id"] == 2
        assert ranked[0]["eta_seconds"] == 200
