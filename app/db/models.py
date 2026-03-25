from datetime import (
    datetime,
    timezone
)
from sqlalchemy import (
    DateTime,
    Float,
    Integer,
    Column,
    String,
    Enum,
    ForeignKey
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
    capacity = Column(
        Integer,
        nullable=False
    )
