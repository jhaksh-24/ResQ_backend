import pytest
from app.core.fleet_state import FleetStateManager
from app.db.models import AmbulanceStatus
import pytest_asyncio

def test_update_location_valid(mock_redis):
    # Setup state
    unit_id = 1
    lat, lng = 12.91, 77.62
    
    # Action
    FleetStateManager.update_location(unit_id, lat, lng)
    
    # Assert
    data = FleetStateManager.get_unit(unit_id)
    assert data is not None
    assert data["latitude"] == "12.91"
    assert data["longitude"] == "77.62"

def test_update_status_valid(mock_redis):
    unit_id = 2
    FleetStateManager.update_status(unit_id, AmbulanceStatus.DISPATCHED.value)
    
    data = FleetStateManager.get_unit(unit_id)
    assert data["status"] == AmbulanceStatus.DISPATCHED.value

def test_get_all_available(mock_redis):
    # Setup some fleet
    FleetStateManager.update_location(10, 12.0, 77.0)
    FleetStateManager.update_status(10, AmbulanceStatus.AVAILABLE.value)
    
    FleetStateManager.update_location(11, 12.1, 77.1)
    FleetStateManager.update_status(11, AmbulanceStatus.DISPATCHED.value)
    
    FleetStateManager.update_location(12, 12.2, 77.2)
    FleetStateManager.update_status(12, AmbulanceStatus.AVAILABLE.value)
    
    # Action
    available = FleetStateManager.get_all_available()
    
    # Assert
    assert len(available) == 2
    ids = [int(a["unit_id"]) for a in available]
    assert 10 in ids
    assert 12 in ids
    assert 11 not in ids

def test_get_unknown_ambulance(mock_redis):
    data = FleetStateManager.get_unit(999)
    assert data is None

def test_get_all_empty(mock_redis):
    # Clear the mock store
    mock_redis.delete("ambulance:1")
    available = FleetStateManager.get_all_available()
    assert available == [] # should be empty

def test_malformed_coordinates(mock_redis):
    # Test setting malformed coordinates
    # FleetStateManager currently converts to float. Let's see how it behaves with strings
    # We should ensure it doesn't crash if passed strings that are floats, but maybe crashes on invalid strings
    FleetStateManager.update_location(3, "12.5", "77.5")
    data = FleetStateManager.get_unit(3)
    assert data["latitude"] == "12.5"
    assert data["longitude"] == "77.5"
    
    with pytest.raises(ValueError):
        FleetStateManager.update_location(4, "not_a_float", "77.5")
