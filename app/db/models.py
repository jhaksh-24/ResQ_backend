from geoalchemy2 import Geometry
from datetime import (
    datetime,
    timezone
)
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    Column,
    String,
    Enum,
    ForeignKey,
    JSON
)
from app.db.session import Base
import enum

class AmbulanceStatus (enum.Enum):
    AVAILABLE = "available"
    DISPATCHED = "dispatched"
    EN_ROUTE_HOSPITAL = "en_route_hospital"
    AT_HOSPITAL = "at_hospital"
    RETURNING = "returning"
    OFFLINE = "offline"

class IncidentStatus (enum.Enum):
    REPORTED = "reported"
    DISPATCHED = "dispatched"
    RESOLVED = "resolved"


class Ambulance (Base):
    __tablename__ = "ambulance"
    id = Column(
        Integer,
        primary_key=True
    )
    vehicle_number = Column(
        String,
        unique=True,
        nullable=False
    )
    status = Column(
        Enum(AmbulanceStatus),
        nullable=False,
        default=AmbulanceStatus.OFFLINE
    )
    latitude = Column(
        Float,
        nullable=False
    )
    longitude = Column(
        Float,
        nullable=False
    )
    station_id = Column(
        Integer,
        ForeignKey("station.id"),
        nullable=False
    )
    updated_at = Column(
        DateTime(
            timezone=True
        ),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

class Station (Base):
    __tablename__ = "station"
    id = Column(
        Integer,
        primary_key=True
    )
    name = Column(
        String,
        nullable=False
    )
    latitude = Column(
        Float,
        nullable=False
    )
    longitude = Column(
        Float,
        nullable=False
    )
    geom = Column(
        Geometry(
            'POINT',
            srid=4326
        )
    )
    capacity = Column(
        Integer,
        nullable=False
    )

class Incident (Base):
    __tablename__ = "incident"
    id = Column(
        Integer,
        primary_key=True
    )
    latitude = Column(
        Float,
        nullable=False
    )
    longitude = Column(
        Float,
        nullable=False
    )
    incident_type = Column(
        String,
        nullable=False
    )
    severity = Column(
        Integer,
        nullable=False,
        default=1
    )
    confidence_score = Column(
        Float,
        nullable=False,
        default=1.0
    )
    ward_id = Column(
        Integer,
        nullable=True
    )
    ward_name = Column(
        String,
        nullable=True
    )
    timestamp = Column(
        DateTime(
            timezone=True
        ),
        default=lambda: datetime.now(timezone.utc)
    )
    status = Column(
        Enum(IncidentStatus),
        nullable=False,
        default=IncidentStatus.REPORTED
    )
    created_at = Column(
        DateTime(
            timezone=True
        ),
        default=lambda: datetime.now(timezone.utc)
    )
    resolved_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=True
    )

class Hospital (Base):
    __tablename__ = "hospital"
    id = Column(
        Integer,
        primary_key=True
    )
    name = Column(
        String,
        nullable=False
    )
    latitude = Column(
        Float,
        nullable=False
    )
    longitude = Column(
        Float,
        nullable=False
    )
    specialties = Column(
        JSON,
        nullable=False,
        default=list
    )
    er_capacity = Column(
        Integer,
        nullable=False
    )
    is_24x7 = Column(
        Boolean,
        nullable=False
    )

class DispatchLog (Base):
    __tablename__ = "dispatch_log"
    id = Column(
        Integer,
        primary_key=True 
    )
    incident_id = Column(
        Integer,
        ForeignKey("incident.id"),
        nullable=False
    )
    ambulance_id = Column(
        Integer,
        ForeignKey("ambulance.id"),
        nullable=False
    )
    hospital_id = Column(
        Integer,
        ForeignKey("hospital.id"),
        nullable=True
    )
    eta_seconds = Column(
        Integer,
        nullable=False
    )
    alternatives_considered = Column(
        Integer,
        default=0
    )
    dispatched_at = Column(
        DateTime(
            timezone=True
        ),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

class Zone (Base):
    __tablename__ = "zone"
    id = Column(
        Integer,
        primary_key=True
    )
    geom = Column(
        Geometry(
            'POLYGON',
            srid=4326
        )
    )
    risk_level = Column(
        Float,
        nullable=False
    )
    created_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(
            timezone=True
        ),
        nullable=True,
        onupdate=lambda: datetime.now(timezone.utc)
    )