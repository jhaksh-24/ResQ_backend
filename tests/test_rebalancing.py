import pytest
import asyncio
from unittest.mock import patch, MagicMock
from app.core.rebalancing import find_rebalance_destination

class FakeZone:
    def __init__(self, id, risk, lat, lng):
        self.id = id
        self.risk_level = risk
        self.lat = lat
        self.lng = lng

@pytest.mark.asyncio
async def test_find_rebalance_destination_tier3():
    zones = [
        FakeZone(1, 0.9, 12.0, 77.0),
        FakeZone(2, 0.1, 12.1, 77.1)
    ]
    
    mock_db = MagicMock()
    mock_db.query().all.return_value = zones
    
    fake_amb = {"unit_id": "1", "latitude": "12.1", "longitude": "77.1"}
    fake_others = [{"unit_id": "2", "latitude": "12.1", "longitude": "77.1"}]
    
    with patch("app.core.rebalancing.FleetStateManager.get_unit", return_value=fake_amb):
        with patch("app.core.rebalancing.FleetStateManager.get_all_available", return_value=fake_others):
            # mock OSRM ETA: getting to zone 1 takes 500s, zone 2 takes 100s
            async def mock_osrm(src_lat, src_lng, dst_lat, dst_lng):
                if dst_lat == 12.0: return 500
                return 100
                
            with patch("app.core.rebalancing.get_osrm_eta", side_effect=mock_osrm):
                # We expect it to pick Zone 1 because vulnerability is huge there
                dest = await find_rebalance_destination(1, mock_db)
                assert dest is not None
                assert dest["target_zone_id"] == 1

@pytest.mark.asyncio
async def test_find_rebalance_destination_no_zones():
    mock_db = MagicMock()
    mock_db.query().all.return_value = []
    
    with patch("app.core.rebalancing.FleetStateManager.get_unit", return_value={"latitude": "12", "longitude": "77"}):
        dest = await find_rebalance_destination(1, mock_db)
        assert dest is None
