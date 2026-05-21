"""
ResQ — Live Incident Ingestion API
====================================
Endpoint for 108 operators to report new incidents.
Receiving an incident here triggers the real-time dispatch engine
and records the incident in the database with confidence_score=1.0.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import asyncio

from app.db.session import get_db
from app.db.models import Incident
from app.core.dispatch_engine import find_best_ambulance
from app.core.logger import get_logger, log_event
import logging

logger = get_logger(__name__)

incidents_router = APIRouter(
    prefix="/incidents",
    tags=["Incidents"]
)

class IncidentReport(BaseModel):
    latitude: float
    longitude: float
    severity: int
    incident_type: str
    patient_condition: Optional[str] = None
    ward_id: Optional[int] = None
    ward_name: Optional[str] = None

async def trigger_dispatch(incident_id: int, lat: float, lon: float):
    """Background task to trigger the dispatch engine."""
    log_event(logger, logging.INFO, "Triggering dispatch engine", incident_id=incident_id, lat=lat, lon=lon)
    try:
        best_unit_id, best_eta = await find_best_ambulance(lat, lon)
        if best_unit_id is not None:
            log_event(logger, logging.INFO, "Dispatch successful", incident_id=incident_id, unit_id=best_unit_id, eta=best_eta)
        else:
            log_event(logger, logging.WARNING, "Dispatch failed - no available ambulances", incident_id=incident_id)
    except Exception as e:
        log_event(logger, logging.ERROR, "Dispatch engine error", incident_id=incident_id, error=str(e))

@incidents_router.post("/report")
async def report_incident(
    report: IncidentReport,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Ingest a live incident report.
    Saves to DB (confidence_score=1.0) and triggers dispatch.
    """
    # 1. Save incident to database
    # In a real system, you might compute weather features here or leave them null
    # for the retraining pipeline to fill in later.
    new_incident = Incident(
        latitude=report.latitude,
        longitude=report.longitude,
        severity=report.severity,
        incident_type=report.incident_type,
        timestamp=datetime.utcnow(),
        confidence_score=1.0,  # Real live data!
        ward_id=report.ward_id,
        ward_name=report.ward_name,
    )
    
    db.add(new_incident)
    db.commit()
    db.refresh(new_incident)
    
    log_event(logger, logging.INFO, "New incident reported", incident_id=new_incident.id, severity=new_incident.severity)
    
    # 2. Trigger dispatch engine in background
    background_tasks.add_task(trigger_dispatch, new_incident.id, float(new_incident.latitude), float(new_incident.longitude))
    
    return {
        "status": "success",
        "message": "Incident reported and dispatch initiated",
        "incident_id": new_incident.id
    }
