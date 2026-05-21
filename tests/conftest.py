import pytest
import asyncio
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(autouse=True)
def mock_redis():
    """Mocks the Redis client used by FleetStateManager."""
    with patch("app.core.fleet_state.redis_client") as mock:
        # Provide a basic fake dictionary for hgetall
        fake_store = {}
        
        def fake_hset(name, mapping=None, **kwargs):
            if name not in fake_store:
                fake_store[name] = {}
            if mapping:
                fake_store[name].update({k: str(v) for k, v in mapping.items()})

        def fake_hmset(name, mapping):
            """hmset — used by fleet_state.py for Redis 3.x compat."""
            if name not in fake_store:
                fake_store[name] = {}
            fake_store[name].update({k: str(v) for k, v in mapping.items()})
            
        def fake_hgetall(name):
            return fake_store.get(name, {})
            
        def fake_scan_iter(match):
            import re
            pattern = match.replace("*", ".*")
            for k in list(fake_store.keys()):
                if re.match(pattern, k):
                    yield k
                    
        def fake_delete(name):
            if name in fake_store:
                del fake_store[name]
                
        def fake_pipeline():
            # A very simple pipeline mock
            pipe = MagicMock()
            return pipe
            
        mock.hset.side_effect = fake_hset
        mock.hmset.side_effect = fake_hmset
        mock.hgetall.side_effect = fake_hgetall
        mock.scan_iter.side_effect = fake_scan_iter
        mock.delete.side_effect = fake_delete
        mock.pipeline.side_effect = fake_pipeline
        
        yield mock

@pytest.fixture
def mock_db():
    """Mocks the SQLAlchemy DB session."""
    session = MagicMock()
    yield session

@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    with TestClient(app) as c:
        yield c
