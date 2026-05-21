"""
ResQ — Bengaluru Station & Hospital Seeder
============================================
Seeds the database with ambulance dispatch centers (stations),
hospitals, and ambulances for Bengaluru.

Station locations are based on existing 108 Ambulance service centers
and major fire stations across Bengaluru's high-risk corridors.

Run from project root:
    python scripts/seed_stations.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.db.models import Station, Hospital, Ambulance, AmbulanceStatus
from geoalchemy2.elements import WKTElement


# ─────────────────────────────────────────────────────────────────────────────
# BENGALURU AMBULANCE DISPATCH CENTERS (STATIONS)
# Based on: 108 Ambulance depots, BBMP fire stations, GVK EMRI station map
# ─────────────────────────────────────────────────────────────────────────────

STATIONS = [
    # ORR Corridor — highest accident density
    ("Silk Board Junction Depot",      12.9171, 77.6227, 3),
    ("Marathahalli 108 Station",       12.9590, 77.6971, 3),
    ("KR Puram Fire Station",          12.9975, 77.6960, 2),
    ("Hebbal Flyover Depot",           13.0450, 77.5900, 2),
    ("Tin Factory Station",            12.9880, 77.6600, 2),

    # South Bengaluru — IT corridor + nightlife zones
    ("Koramangala Fire Station",       12.9352, 77.6245, 3),
    ("BTM Layout 108 Depot",           12.9166, 77.6101, 2),
    ("Electronic City Phase 1 Depot",  12.8458, 77.6618, 2),
    ("HSR Layout Station",             12.9116, 77.6389, 2),
    ("Bommanahalli Station",           12.8917, 77.6372, 2),
    ("Bannerghatta Road Depot",        12.8946, 77.5972, 2),

    # North Bengaluru — industrial + airport corridor
    ("Peenya Industrial Depot",        13.0280, 77.5190, 2),
    ("Yeshwanthpur Fire Station",      13.0220, 77.5510, 2),
    ("Yelahanka Air Force Stn Depot",  13.1007, 77.5963, 2),
    ("Airport Road Depot",             13.0800, 77.6100, 2),

    # East — IT + residential
    ("Whitefield 108 Station",         12.9698, 77.7500, 3),
    ("ITPL Depot",                     12.9856, 77.7271, 2),
    ("Bellandur Fire Station",         12.9257, 77.6779, 2),
    ("Sarjapur Road Depot",            12.9060, 77.6870, 2),

    # Central Bengaluru
    ("MG Road Central Station",        12.9762, 77.6033, 2),
    ("Shivajinagar Fire Station",      12.9847, 77.5990, 2),
    ("Indiranagar 108 Depot",          12.9784, 77.6408, 2),

    # West Bengaluru
    ("Rajajinagar Fire Station",       12.9940, 77.5530, 2),
    ("Vijayanagar Depot",              12.9722, 77.5200, 2),

    # South-West
    ("Jayanagar Fire Station",         12.9299, 77.5826, 2),
    ("JP Nagar 108 Depot",             12.9082, 77.5852, 2),
    ("Banashankari Depot",             12.9252, 77.5460, 2),
    ("Kanakapura Road Station",        12.8820, 77.5740, 2),

    # North-East fill
    ("Hennur Depot",                   13.0430, 77.6400, 2),
    ("Horamavu Station",               13.0211, 77.6527, 2),
    ("Ramamurthy Nagar Depot",         13.0050, 77.6600, 2),
]

# ─────────────────────────────────────────────────────────────────────────────
# BENGALURU HOSPITALS (with specialties and ER capacity)
# ─────────────────────────────────────────────────────────────────────────────

HOSPITALS = [
    # (name, lat, lon, specialties, er_capacity, is_24x7)
    ("St. John's Medical College Hospital",    12.9288, 77.6207, ["trauma", "cardiac", "neurological", "burns", "respiratory"], 45, True),
    ("Manipal Hospital - HAL Airport Road",    12.9600, 77.6480, ["trauma", "cardiac", "neurological", "burns"], 40, True),
    ("Narayana Health City",                   12.8488, 77.6755, ["cardiac", "neurological", "trauma"], 50, True),
    ("Apollo Hospital - Bannerghatta",         12.8928, 77.5968, ["trauma", "cardiac", "burns", "neurological"], 35, True),
    ("Fortis Hospital - Cunningham Road",      12.9920, 77.5870, ["trauma", "cardiac", "neurological"], 30, True),
    ("Sakra World Hospital - Bellandur",       12.9257, 77.6799, ["trauma", "cardiac", "respiratory"], 25, True),
    ("Columbia Asia - Hebbal",                 13.0390, 77.5930, ["trauma", "cardiac", "respiratory"], 20, True),
    ("Sparsh Hospital - Infantry Road",        12.9830, 77.5940, ["trauma", "neurological"], 20, True),
    ("BGS Gleneagles - Kengeri",               12.9100, 77.4920, ["trauma", "cardiac", "burns"], 25, True),
    ("Aster CMI - Hebbal",                     13.0410, 77.5965, ["trauma", "cardiac", "respiratory", "neurological"], 30, True),
    ("MS Ramaiah Memorial Hospital",           13.0310, 77.5650, ["trauma", "cardiac", "burns"], 25, True),
    ("NIMHANS",                                12.9417, 77.5890, ["neurological", "trauma"], 30, True),
    ("Victoria Hospital",                      12.9570, 77.5730, ["trauma", "burns", "general"], 60, True),
    ("KC General Hospital - Malleswaram",      13.0050, 77.5700, ["trauma", "cardiac", "general"], 35, True),
    ("Bowring Hospital",                       12.9800, 77.6050, ["trauma", "general", "respiratory"], 40, True),
    ("Jayadeva Institute of Cardiology",       12.9180, 77.5990, ["cardiac"], 35, True),
    ("Bangalore Baptist Hospital",             12.8920, 77.6060, ["trauma", "general", "respiratory"], 20, True),
    ("Sagar Hospital - Kumaraswamy Layout",    12.9080, 77.5610, ["trauma", "cardiac", "burns"], 20, True),
    ("Narayana Multispeciality - HSR Layout",  12.9130, 77.6350, ["trauma", "cardiac", "respiratory"], 20, True),
    ("Cloudnine Hospital - Jayanagar",         12.9300, 77.5830, ["general", "respiratory"], 15, False),
]


def seed():
    db = SessionLocal()
    try:
        # ── Seed Stations ────────────────────────────────────────────────
        existing_stations = db.query(Station).count()
        if existing_stations > 0:
            print(f"WARN: Stations table already has {existing_stations} rows. Skipping station seed.")
        else:
            for name, lat, lon, capacity in STATIONS:
                station = Station(
                    name=name,
                    latitude=lat,
                    longitude=lon,
                    geom=WKTElement(f"POINT({lon} {lat})", srid=4326),
                    capacity=capacity,
                )
                db.add(station)
            db.flush()
            print(f"SUCCESS: Seeded {len(STATIONS)} stations")

        # ── Seed Hospitals ───────────────────────────────────────────────
        existing_hospitals = db.query(Hospital).count()
        if existing_hospitals > 0:
            print(f"WARN: Hospitals table already has {existing_hospitals} rows. Skipping hospital seed.")
        else:
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
            print(f"SUCCESS: Seeded {len(HOSPITALS)} hospitals")

        # ── Seed Ambulances (2 per station) ──────────────────────────────
        existing_ambulances = db.query(Ambulance).count()
        if existing_ambulances > 0:
            print(f"WARN: Ambulances table already has {existing_ambulances} rows. Skipping ambulance seed.")
        else:
            stations = db.query(Station).all()
            amb_count = 0
            for station in stations:
                for i in range(station.capacity):
                    amb = Ambulance(
                        vehicle_number=f"KA-01-{station.id:02d}-{i+1:02d}",
                        status=AmbulanceStatus.AVAILABLE,
                        latitude=station.latitude,
                        longitude=station.longitude,
                        station_id=station.id,
                    )
                    db.add(amb)
                    amb_count += 1
            db.flush()
            print(f"SUCCESS: Seeded {amb_count} ambulances ({station.capacity} per station based on capacity)")

        db.commit()
        print("\nSUCCESS: Database seeded successfully!")

        # Print summary
        print(f"\nSummary:")
        print(f"  Stations:   {db.query(Station).count()}")
        print(f"  Hospitals:  {db.query(Hospital).count()}")
        print(f"  Ambulances: {db.query(Ambulance).count()}")

    except Exception as e:
        db.rollback()
        print(f"ERROR: Seeding failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("ResQ Database Seeder")
    print("=" * 50)
    seed()
