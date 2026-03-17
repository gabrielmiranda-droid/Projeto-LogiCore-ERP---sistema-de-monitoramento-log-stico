from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class TelemetryIn(BaseModel):
    vehicle_id: int
    timestamp: datetime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    speed_kmh: float = Field(ge=0, le=200)
    fuel_level: float = Field(ge=0, le=100)
    cargo_occupancy: float = Field(ge=0, le=100)
    route_id: int


class TelemetryRead(ORMModel):
    id: int | None = None
    vehicle_id: int
    route_id: int
    timestamp: datetime
    latitude: float
    longitude: float
    speed_kmh: float
    fuel_level: float
    cargo_occupancy: float
