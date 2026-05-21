import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_api():
    print("Testing GET /zones/mesh")
    response = client.get("/zones/mesh")
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Features count: {len(data['features'])}")
    print(f"First feature: {data['features'][0]['properties'] if data['features'] else 'None'}")
    
    print("\nTesting GET /zones/risk-surface?resolution=20")
    response = client.get("/zones/risk-surface?resolution=20")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Metadata: {data.get('metadata')}")

if __name__ == "__main__":
    test_api()
