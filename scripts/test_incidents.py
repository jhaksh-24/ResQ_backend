import sys
import os
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_incident_report():
    print("Testing POST /incidents/report")
    payload = {
        "latitude": 12.9171,
        "longitude": 77.6227,
        "severity": 4,
        "incident_type": "trauma",
        "patient_condition": "Critical accident",
        "ward_id": 1,
        "ward_name": "Silk Board"
    }
    
    response = client.post("/incidents/report", json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

if __name__ == "__main__":
    test_incident_report()
