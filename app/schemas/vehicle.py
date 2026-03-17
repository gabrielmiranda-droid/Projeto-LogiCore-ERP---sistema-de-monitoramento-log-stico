from datetime import datetime

from app.schemas.common import ORMModel, TimestampedSchema


class VehicleRead(TimestampedSchema):
    code: str
    license_plate: str
    model: str
    capacity_kg: float
    status: str
    driver_id: int | None
    route_id: int | None


class VehicleSummaryRead(ORMModel):
    id: int
    code: str
    license_plate: str
    model: str
    vehicle_status: str
    route_id: int | None
    route_code: str | None
    route_name: str | None
    speed_kmh: float | None
    fuel_level: float | None
    cargo_occupancy: float | None
    timestamp: datetime | None


class VehicleOverviewRead(ORMModel):
    vehicle: dict
    planned_route: dict | None
    recent_alerts: list[dict]
    recent_telemetry: list[dict]
    operational_summary: dict
