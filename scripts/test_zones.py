import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.zones import generate_zone_mesh
from app.db.session import SessionLocal

def test_mesh_generation():
    db = SessionLocal()
    try:
        print("Testing zone generation...")
        res = generate_zone_mesh(max_additional_vertices=120, risk_threshold=0.3, db=db)
        print("Result:")
        print(f"Status: {res['status']}")
        print(f"Zones Generated: {res['zones_generated']}")
        print(f"Stations Used: {res['stations_used']}")
        print("Done!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_mesh_generation()
