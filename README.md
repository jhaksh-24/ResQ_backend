# ResQ — Backend Core
> AI-Native Dispatch Optimisation Engine for Urban Emergency Medical Services

[![Python](https://img.shields.io/badge/Python-3.11+-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green)](https://fastapi.tiangolo.com)
[![PostGIS](https://img.shields.io/badge/PostGIS-3.4+-blue)](https://postgis.net)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Status](https://img.shields.io/badge/Status-In%20Development-orange)]()

---

## Overview

ResQ is an ETA-minimisation dispatch engine for urban ambulance fleets. It replaces proximity-based dispatch — the industry default — with a system that evaluates every available unit across the entire fleet on predicted arrival time under live traffic conditions, rebalances fleet distribution continuously, and routes patients to the optimal hospital on every dispatch.

The backend is the intelligence layer. It exposes a FastAPI surface consumed by the mobile frontend and dispatcher dashboard.

---

## Core Problem

| Dimension | Proximity Dispatch | ResQ |
|---|---|---|
| Dispatch logic | Nearest unit by distance | Fastest unit by real-time ETA |
| Fleet distribution | Static, drifts through shift | Dynamic three-tier rebalancing |
| Demand anticipation | Reactive only | Probabilistic spatial pre-positioning |
| Zone geometry | Circular — overlaps and blind spots | Irregular polygon mesh |
| Hospital routing | Nearest facility | Ranked by ER capacity, specialty, and ETA |

Academic literature on optimised dispatch reports response time reductions of up to 42% over nearest-unit approaches in simulation (Zarkeshzadeh et al., 2015). ResQ targets improvements at the upper end of this range for the Indian urban context.

---

## Architecture

Five independently deployable and testable engines, unified behind a FastAPI layer.

```
                    ┌─────────────────────────────────┐
                    │         ResQ Backend Core        │
                    └─────────────┬───────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
    ┌─────▼──────┐         ┌──────▼─────┐         ┌──────▼─────┐
    │  Spatial   │         │  Dispatch  │         │  Hospital  │
    │  Engine    │         │  Engine    │         │  Router    │
    └─────┬──────┘         └──────┬─────┘         └──────┬─────┘
          │                       │                       │
    ┌─────▼──────┐         ┌──────▼─────┐                │
    │  Demand    │         │Rebalancing │                │
    │  Surface   │         │  Engine    │                │
    └────────────┘         └────────────┘                │
          │                       │                       │
          └───────────────────────┴───────────────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │        FastAPI Layer         │
                    │    (consumed by frontend)    │
                    └─────────────────────────────┘
```

---

## Engines

### Spatial Engine

Models the city as a dynamic probabilistic risk landscape rather than a static map. Operates in three stages:

**Stage 1 — Risk Surface Generation**

Builds a continuous probability surface using a non-parametric spatial density model. No fixed distribution is assumed — the surface shape is entirely data-driven from:
- Historical incident records with location and timestamp
- Population density per micro-zone
- Road network topology and traffic volume corridors
- High-density points of interest: tech parks, malls, hospitals, stadiums
- Temporal patterns: time of day, day of week, seasonal variation

**Stage 2 — Surface Evolution Prediction**

A sequential ML model predicts how the risk surface shifts over the next N minutes based on live traffic conditions, time-of-day patterns, ongoing incidents in the system, and historical shift patterns at equivalent timestamps.

**Stage 3 — Adaptive Mesh Generation**

Both surfaces — current and predicted — feed into a constrained mesh generation model that drapes an irregular polygon mesh over the risk landscape:
- High-risk zones produce small, dense polygons for maximum response density
- Low-risk zones produce large, sparse polygons for efficient resource distribution
- Mesh is stitched to physical geography: rivers, flyovers, one-ways, administrative boundaries
- Dispatch station vertices are fixed infrastructure; zone boundaries are software-defined and recalculated periodically

---

### Dispatch Engine

Every ambulance in the fleet is a live node: GPS coordinate, status flag, and real-time ETA computation.

On every incident:
1. All available units across the entire fleet are evaluated — zone lines do not exist during active dispatch
2. ETA is computed under live traffic conditions via OSRM, with Google Maps / HERE as the primary real-time feed
3. The unit with minimum ETA is dispatched
4. The full decision is written to the audit log: unit selected, ETA computed, all alternatives evaluated, timestamp

**Free-agent rule:** A dispatched unit can be reassigned mid-field if it holds the lowest ETA to a new incident, without returning to base first. If no qualifying incident arises before handoff completes, the unit does not return home — it flows directly into the rebalancing process and routes to the highest-demand station.

**No-withholding policy:** Units are never held back to protect zone coverage minimums. Coverage gaps trigger automatic mutual aid from the least-stressed neighbouring zone, in parallel with dispatch — never instead of it.

**Audit guarantee:** Every dispatch decision is fully logged with all alternatives considered. No decision is undocumented.

---

### Rebalancing Engine

Fleet distribution drifts through a shift as units are dispatched. Three concurrent tiers correct this continuously without blocking active dispatch decisions.

| Tier | Trigger | Action |
|---|---|---|
| **Tier 1 — Urgent** | Zone reaches zero units | Immediate pull from nearest surplus station. Coverage over efficiency. |
| **Tier 2 — Scheduled** | Every N hours | Optimisation pass against predicted demand. Units move only if ERT gain exceeds relocation cost. |
| **Tier 3 — Passive** | Post-handoff unit return | Unit routes to highest-demand station rather than home base. Zero added overhead. |

While a unit is en route to hospital, the backend pre-computes its optimal post-handoff destination. When handoff completes, the next assignment is already set — zero decision latency at the moment the unit becomes available.

---

### Hospital Router

Nearest hospital and best hospital are not the same. On every dispatch, candidate hospitals are ranked by:
1. Real-time traffic ETA
2. Specialty match with incident type: trauma, cardiac, burns, neuro, general
3. Current ER capacity and operational status
4. 24/7 availability

Top recommendation plus two to three alternatives are surfaced to the ambulance crew via the Crew App. Crew retains final authority and can override at any time. All overrides are logged and feed back into hospital weighting over time. Repeated overrides for a specific hospital trigger a data quality review.

---

## Objective Function

All rebalancing and pre-positioning decisions are evaluated against a single function — Expected Response Time (ERT):

```
ERT = Σ P(i) × T(i)
```

- `P(i)` — predicted probability of an incident in zone i, derived from the demand surface
- `T(i)` — travel time from the nearest available unit to zone i under current traffic

Every engine decision that reduces ERT is correct. Every decision that increases it is not.

---

## Data Inputs

| Signal | Source | Refresh |
|---|---|---|
| Historical incidents | Bangalore Traffic Police / RTI / public records | Periodic |
| Road network | OpenStreetMap via OSMnx | Periodic |
| Offline routing | OSRM on cached Bengaluru road graph | Every 15 minutes |
| Population density | Census of India | Annual |
| Live traffic | Google Maps Platform / HERE Maps API | Real-time |
| Hospital capacity | Manual entry + API where available | Near real-time |
| Weather | OpenWeatherMap API | Real-time |
| Points of interest | OpenStreetMap / Google Places | Periodic |

OSRM serves as the offline routing fallback when live traffic APIs are unavailable. Dispatch decisions are never blocked by upstream API failure.

---

## Deployment Target: Bengaluru

Bengaluru is the primary deployment target — not because it is easy but because it is one of the hardest urban road networks in India to optimise ETA dispatch on. The ORR corridor, Silk Board junction, Hebbal flyover, and inner-city density represent a genuine stress test. If ResQ works in Bengaluru, it works anywhere.

Future expansion: Hyderabad, Chennai, Mumbai, Delhi-NCR.

---

## Directory Structure

```
resq-backend/
│
├── app/
│   ├── main.py                   # FastAPI entry point
│   ├── config.py                 # Environment and configuration
│   │
│   ├── api/                      # Route definitions
│   │   ├── dispatch.py           # Dispatch endpoints
│   │   ├── fleet.py              # Fleet state endpoints
│   │   ├── hospital.py           # Hospital routing endpoints
│   │   └── zones.py              # Zone mesh endpoints
│   │
│   ├── core/                     # Core business logic
│   │   ├── dispatch_engine.py    # ETA computation and unit selection
│   │   ├── rebalancing.py        # Three-tier rebalancing logic
│   │   ├── hospital_router.py    # Hospital ranking logic
│   │   └── fleet_state.py        # Live fleet state management
│   │
│   ├── spatial/                  # Spatial engine
│   │   ├── mesh_generator.py     # Polygon mesh generation
│   │   ├── risk_surface.py       # Stage 1: current risk surface
│   │   ├── surface_predictor.py  # Stage 2: surface evolution prediction
│   │   └── zone_manager.py       # Zone boundary management
│   │
│   ├── ml/                       # ML model definitions and inference
│   │   ├── demand_model.py       # Demand surface model
│   │   ├── mesh_model.py         # Mesh generation model
│   │   └── model_registry.py     # Model loading and versioning
│   │
│   ├── data/                     # Data ingestion and processing
│   │   ├── ingestion/
│   │   │   ├── osm_loader.py     # OpenStreetMap / OSMnx pipeline
│   │   │   ├── incident_loader.py# Historical incident data
│   │   │   └── live_traffic.py   # Real-time traffic feed
│   │   └── processing/
│   │       ├── cleaner.py        # Data cleaning and validation
│   │       └── feature_builder.py# Feature engineering for ML
│   │
│   ├── db/                       # Database layer
│   │   ├── models.py             # ORM models
│   │   ├── session.py            # DB session management
│   │   └── migrations/           # Alembic migrations
│   │
│   └── utils/
│       ├── geo.py                # Geospatial helper functions
│       ├── logger.py             # Structured logging
│       └── audit.py             # Dispatch decision audit trail
│
├── models/                       # Trained ML model artifacts
│   └── .gitkeep
│
├── data/
│   ├── raw/
│   └── processed/
│
├── tests/
│   ├── test_dispatch.py
│   ├── test_rebalancing.py
│   ├── test_spatial.py
│   └── test_hospital_router.py
│
├── scripts/
│   ├── load_bengaluru_osm.py     # Initial OSM road network load
│   └── simulate_incidents.py     # Synthetic incident generation for
│                                 # dispatch engine testing without real data
├── docs/
│   └── architecture.md
│
├── requirements.txt
├── .env.example
├── .gitignore
├── Dockerfile
└── README.md
```

---

## Getting Started

> Active development. Setup instructions will be updated as the stack stabilises.

### Prerequisites

- Python 3.11+
- PostgreSQL with PostGIS extension — spatial queries for polygon mesh storage and zone boundary lookups
- Redis — fleet state management and real-time caching
- OSRM — offline routing engine, requires Bengaluru road graph (see `scripts/load_bengaluru_osm.py`)

### Installation

```bash
git clone https://github.com/[org]/resq-backend.git
cd resq-backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# configure environment variables
uvicorn app.main:app --reload
```

### Running the Simulation

`simulate_incidents.py` generates synthetic incident data over the Bengaluru road network, allowing full dispatch engine testing without requiring real incident records. Use this to validate ETA computation, rebalancing triggers, and audit logging before connecting live data sources.

```bash
python scripts/simulate_incidents.py --incidents 1000 --duration-hours 8
```

---

## Research Foundation

- Zarkeshzadeh et al. (2015) — ETA-optimised dispatch demonstrates up to 42% response time reduction over nearest-unit methods in simulation
- Nakada et al. (2024) — Fleet rebalancing interventions produce statistically significant response time reductions in urban EMS systems

---

## Accountability

ResQ is a logistics and routing coordination layer. All medical decisions are made exclusively by licensed professionals — ambulance crew in the field and hospital staff on arrival. ResQ is accountable for its algorithm and its technology. Clinical outcomes are outside its domain.

Every dispatch decision is logged with timestamp, unit selected, ETA computed, all alternatives considered, and outcome. The system never makes an undocumented decision.

---

## Team

| Name | USN | Role |
|---|---|---|
| Akshat Kumar Jha | 1WA24CS031 | Backend Core, Spatial Engine, ML Pipeline, System Architecture |
| Aditya Dadheech | 1WA24CS018 | Backend, ML Pipeline, Data Pipeline, Incident Data Sourcing |
| Arush Mandhan | 1WA24CS054 | Frontend Core, API Integration, Interaction & Response Engineering |
| Aryan Surya K.S | 1WA24CS060 | Frontend, API Integration, Interaction & Response Engineering, Logo Design |

*B.M.S. College of Engineering, Dept. of Computer Science & Engineering, Bengaluru*
*Mobile Application Development — Semester 4, 2026*

---

## Roadmap

- [ ] Bengaluru OSM road network loading
- [ ] Historical incident data pipeline
- [ ] Stage 1: Risk surface generation
- [ ] Stage 2: Surface evolution prediction
- [ ] Stage 3: Adaptive mesh generation
- [ ] ETA dispatch engine
- [ ] Three-tier rebalancing engine
- [ ] Hospital routing engine
- [ ] FastAPI layer
- [ ] Simulation validation over Bengaluru incident data
- [ ] Live deployment trial
- [ ] Reinforcement learning based rebalancing calibration
- [ ] BBMP traffic signal integration

---

*ResQ is in active development. Contributions, feedback, and questions welcome.*