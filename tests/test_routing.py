import pytest
from app.core.routing import get_osrm_eta
from app.utils.distance import haversine_distance
from unittest.mock import patch, MagicMock
import httpx

def test_haversine_distance():
    # Test distance between two known points
    dist = haversine_distance(12.91, 77.62, 12.92, 77.63)
    assert dist > 0
    # Same point should be 0
    assert haversine_distance(12.0, 77.0, 12.0, 77.0) == 0.0

@pytest.mark.asyncio
async def test_get_osrm_eta_success():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "code": "Ok",
            "routes": [{"duration": 450}]
        }
        mock_get.return_value = mock_response
        
        eta = await get_osrm_eta(12.0, 77.0, 12.1, 77.1)
        assert eta == 450

@pytest.mark.asyncio
async def test_get_osrm_eta_fallback_on_httperror():
    with patch("httpx.AsyncClient.get", side_effect=httpx.HTTPError("Server down")):
        # Should catch HTTPError and return haversine fallback
        # dist is approx 15km for 0.1 deg diff
        # formula gives (dist / 40.0) * 3600 ~ 1400 seconds
        eta = await get_osrm_eta(12.0, 77.0, 12.1, 77.1)
        assert eta == 999999

@pytest.mark.asyncio
async def test_get_osrm_eta_fallback_on_bad_json():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {"code": "NoRoute"}
        mock_get.return_value = mock_response
        
        eta = await get_osrm_eta(12.0, 77.0, 12.1, 77.1)
        assert eta > 0
