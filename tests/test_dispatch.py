import pytest
import asyncio
from unittest.mock import patch
from app.core.dispatch_engine import find_best_ambulance

@pytest.mark.asyncio
async def test_find_best_ambulance_zero_availability():
    # Mock FleetStateManager to return no available ambulances
    with patch("app.core.dispatch_engine.FleetStateManager.get_dispatchable_units", return_value=[]):
        unit_id, eta = await find_best_ambulance(12.0, 77.0)
        assert unit_id is None
        assert eta is None

@pytest.mark.asyncio
async def test_find_best_ambulance_osrm_success():
    fake_ambulances = [
        {"unit_id": 1, "latitude": "12.91", "longitude": "77.62"},
        {"unit_id": 2, "latitude": "12.92", "longitude": "77.63"}
    ]
    with patch("app.core.dispatch_engine.FleetStateManager.get_dispatchable_units", return_value=fake_ambulances):
        # Mock OSRM ETA: returns 300 for unit 1, 150 for unit 2
        async def mock_osrm(alat, alng, ilat, ilng):
            if alat == 12.91:
                return 300
            return 150
            
        with patch("app.core.dispatch_engine.get_osrm_eta", side_effect=mock_osrm):
            unit_id, eta = await find_best_ambulance(12.90, 77.60)
            assert unit_id == 2
            assert eta == 150

@pytest.mark.asyncio
async def test_find_best_ambulance_osrm_failure_fallback():
    # If OSRM fails, get_osrm_eta handles fallback internally.
    # We should test that find_best_ambulance can handle large ETAs or fallback values correctly.
    # Let's mock it to return high ETAs (which get_osrm_eta does on failure by defaulting to Haversine-based ETA).
    fake_ambulances = [
        {"unit_id": 1, "latitude": "12.91", "longitude": "77.62"},
        {"unit_id": 2, "latitude": "12.92", "longitude": "77.63"}
    ]
    with patch("app.core.dispatch_engine.FleetStateManager.get_dispatchable_units", return_value=fake_ambulances):
        async def mock_osrm(alat, alng, ilat, ilng):
            return 999999 # Simulating a failure or unreachable state
            
        with patch("app.core.dispatch_engine.get_osrm_eta", side_effect=mock_osrm):
            unit_id, eta = await find_best_ambulance(12.90, 77.60)
            assert unit_id == 1
            assert eta == 999999

@pytest.mark.asyncio
async def test_find_best_ambulance_equidistant():
    # Two ambulances with same ETA, should pick the first one
    fake_ambulances = [
        {"unit_id": 1, "latitude": "12.91", "longitude": "77.62"},
        {"unit_id": 2, "latitude": "12.92", "longitude": "77.63"}
    ]
    with patch("app.core.dispatch_engine.FleetStateManager.get_dispatchable_units", return_value=fake_ambulances):
        async def mock_osrm(alat, alng, ilat, ilng):
            return 200
            
        with patch("app.core.dispatch_engine.get_osrm_eta", side_effect=mock_osrm):
            unit_id, eta = await find_best_ambulance(12.90, 77.60)
            assert unit_id == 1
            assert eta == 200
