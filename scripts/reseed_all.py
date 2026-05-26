import sys
import os
import random
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.db.models import Station, Hospital, Ambulance, AmbulanceStatus, Zone, DispatchLog, Incident
from geoalchemy2.elements import WKTElement
import redis

# Import Wards and Hospitals
from scripts.generate_synthetic_incidents import WARDS
from scripts.seed_stations import HOSPITALS
from app.core.fleet_state import FleetStateManager
from app.spatial.risk_surface import build_risk_surface
from app.spatial.mesh_generator import generate_mesh

def reseed_everything():
    db = SessionLocal()
    r = redis.Redis.from_url('redis://localhost:6379/0', decode_responses=True)
    
    try:
        # 1. CLEAR DB AND REDIS
        print("Clearing database and Redis...")
        db.query(DispatchLog).delete()
        db.query(Incident).delete()
        db.query(Ambulance).delete()
        db.query(Hospital).delete()
        db.query(Station).delete()
        db.query(Zone).delete()
        db.commit()
        r.flushdb()
        print("Cleared successfully.")

        # 2. SEED HOSPITALS
        print("\nSeeding Hospitals...")
        for name, lat, lon, specs, cap, is247 in HOSPITALS:
            hospital = Hospital(
                name=name,
                latitude=lat,
                longitude=lon,
                specialties=specs,
                er_capacity=cap,
                is_24x7=is247,
            )
            db.add(hospital)
        db.flush()

        # 3. SEED STATIONS (Weighted by Ward Risk)
        print("\nSeeding Stations based on Ward Risk Weights...")
        # Wards format: (name, lat_centre, lon_centre, risk_weight, area_sqkm, population_2021est)
        for name, lat, lon, risk_weight, area, _ in WARDS:
            # Generate 2 to 5 stations per ward depending on risk weight (max risk is ~3.8)
            num_stations = max(2, int(risk_weight * 1.5))
            
            noise_deg = (np.sqrt(area) * 0.5) / 111.0 # 0.5km spread
            
            for i in range(num_stations):
                s_lat = lat + np.random.normal(0, noise_deg)
                s_lon = lon + np.random.normal(0, noise_deg)
                
                # Base capacity on risk weight
                capacity = max(10, int(risk_weight * 8)) # 10 to ~30 ambulances per station
                
                station = Station(
                    name=f"{name} Dispatch Center {i+1}",
                    latitude=s_lat,
                    longitude=s_lon,
                    geom=WKTElement(f"POINT({s_lon} {s_lat})", srid=4326),
                    capacity=capacity,
                )
                db.add(station)
        
        db.flush()
        stations = db.query(Station).all()
        print(f"Created {len(stations)} dense dispatch centers across Bengaluru.")

        # 4. SEED AMBULANCES (and sync to Redis immediately)
        print("\nSeeding Ambulances and syncing to Redis...")
        amb_count = 0
        for station in stations:
            for i in range(station.capacity):
                amb = Ambulance(
                    vehicle_number=f"KA-01-{station.id:03d}-{i+1:03d}",
                    status=AmbulanceStatus.AVAILABLE,
                    latitude=station.latitude,
                    longitude=station.longitude,
                    station_id=station.id,
                )
                db.add(amb)
                db.flush() # flush to get amb.id
                
                # Sync to Redis right now
                FleetStateManager.update_location(amb.id, amb.latitude, amb.longitude)
                FleetStateManager.update_status(amb.id, AmbulanceStatus.AVAILABLE.value)
                
                amb_count += 1
                
        print(f"Created and synced {amb_count} ambulances distributed by risk weight.")

        # 5. GENERATE ADAPTIVE MESH
        print("\nGenerating Adaptive Risk Mesh...")
        surface = build_risk_surface()
        station_points = [(s.latitude, s.longitude) for s in stations]
        
        # Inject up to 200 extra vertices for high-risk zones
        zones = generate_mesh(
            station_points=station_points,
            risk_surface=surface,
            max_additional_vertices=200,
            risk_threshold=0.25,
        )
        
        import json
        from geoalchemy2.functions import ST_GeomFromGeoJSON
        for zone_data in zones:
            poly = zone_data["polygon"]
            geojson_str = json.dumps(poly.__geo_interface__)
            new_zone = Zone(
                geom=ST_GeomFromGeoJSON(geojson_str),
                risk_level=zone_data["risk_level"],
            )
            db.add(new_zone)
        
        print(f"Generated {len(zones)} dynamic Voronoi mesh zones.")

        db.commit()
        print("\nSUCCESS: Reseeding & Redis Sync & Mesh Generation complete!")
        print(f"Stations: {len(stations)}")
        print(f"Ambulances: {amb_count}")
        print(f"Zones: {len(zones)}")

    except Exception as e:
        db.rollback()
        print(f"ERROR: Seeding failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    reseed_everything()
