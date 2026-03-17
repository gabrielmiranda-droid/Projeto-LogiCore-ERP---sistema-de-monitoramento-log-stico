from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Alert, Route, TelemetryEvent, Vehicle
from app.repositories.telemetry_repository import TelemetryRepository
from app.repositories.vehicle_repository import VehicleRepository
from app.schemas.vehicle import VehicleOverviewRead, VehicleRead, VehicleSummaryRead
from app.services.routing_service import routing_service


router = APIRouter(prefix="/vehicles", tags=["Vehicles"])
vehicle_repository = VehicleRepository()
telemetry_repository = TelemetryRepository()


@router.get("", response_model=list[VehicleRead])
def list_vehicles(db: Session = Depends(get_db)) -> list[VehicleRead]:
    vehicles = vehicle_repository.list_with_latest_positions(db)
    return [VehicleRead.model_validate(vehicle) for vehicle in vehicles]


@router.get("/summary", response_model=list[VehicleSummaryRead])
def list_vehicle_summary(db: Session = Depends(get_db)) -> list[VehicleSummaryRead]:
    latest_events_subquery = (
        select(TelemetryEvent.vehicle_id, func.max(TelemetryEvent.timestamp).label("last_timestamp"))
        .group_by(TelemetryEvent.vehicle_id)
        .subquery()
    )
    rows = db.execute(
        select(
            Vehicle.id,
            Vehicle.code,
            Vehicle.license_plate,
            Vehicle.model,
            Vehicle.status.label("vehicle_status"),
            Vehicle.route_id,
            Route.code.label("route_code"),
            Route.name.label("route_name"),
            TelemetryEvent.speed_kmh,
            TelemetryEvent.fuel_level,
            TelemetryEvent.cargo_occupancy,
            TelemetryEvent.timestamp,
        )
        .join(latest_events_subquery, latest_events_subquery.c.vehicle_id == Vehicle.id, isouter=True)
        .join(Route, Route.id == Vehicle.route_id, isouter=True)
        .join(
            TelemetryEvent,
            (TelemetryEvent.vehicle_id == Vehicle.id)
            & (TelemetryEvent.timestamp == latest_events_subquery.c.last_timestamp),
            isouter=True,
        )
        .order_by(Vehicle.code)
    ).mappings()
    return [VehicleSummaryRead.model_validate(dict(row)) for row in rows]


@router.get("/{vehicle_id}/overview", response_model=VehicleOverviewRead)
def get_vehicle_overview(vehicle_id: int, db: Session = Depends(get_db)) -> VehicleOverviewRead:
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Veiculo nao encontrado")

    latest_event = telemetry_repository.latest_for_vehicle(db, vehicle_id)
    recent_telemetry = telemetry_repository.list_vehicle_history(db, vehicle_id, limit=30)
    recent_alerts = db.execute(
        select(Alert)
        .where(Alert.vehicle_id == vehicle_id)
        .order_by(Alert.created_at.desc())
        .limit(10)
    ).scalars().all()
    planned_route = routing_service.get_vehicle_planned_route(db, vehicle_id)

    payload = {
        "vehicle": {
            "id": vehicle.id,
            "code": vehicle.code,
            "license_plate": vehicle.license_plate,
            "model": vehicle.model,
            "vehicle_status": vehicle.status,
            "route_id": vehicle.route_id,
            "latest_position": None
            if latest_event is None
            else {
                "latitude": latest_event.latitude,
                "longitude": latest_event.longitude,
                "speed_kmh": latest_event.speed_kmh,
                "fuel_level": latest_event.fuel_level,
                "cargo_occupancy": latest_event.cargo_occupancy,
                "timestamp": latest_event.timestamp.isoformat(),
            },
        },
        "planned_route": planned_route,
        "recent_alerts": [
            {
                "id": alert.id,
                "alert_type": getattr(alert.alert_type, "value", str(alert.alert_type)),
                "severity": alert.severity,
                "message": alert.message,
                "created_at": alert.created_at.isoformat(),
                "route_id": alert.route_id,
                "telemetry_event_id": alert.telemetry_event_id,
            }
            for alert in recent_alerts
        ],
        "recent_telemetry": [
            {
                "id": event.id,
                "timestamp": event.timestamp.isoformat(),
                "latitude": event.latitude,
                "longitude": event.longitude,
                "speed_kmh": event.speed_kmh,
                "fuel_level": event.fuel_level,
                "cargo_occupancy": event.cargo_occupancy,
                "route_id": event.route_id,
            }
            for event in reversed(recent_telemetry)
        ],
        "operational_summary": {
            "last_update": latest_event.timestamp.isoformat() if latest_event is not None else None,
            "speed_kmh": latest_event.speed_kmh if latest_event is not None else None,
            "fuel_level": latest_event.fuel_level if latest_event is not None else None,
            "cargo_occupancy": latest_event.cargo_occupancy if latest_event is not None else None,
            "route_id": vehicle.route_id,
            "status": vehicle.status,
            "recent_alert_count": len(recent_alerts),
        },
    }
    return VehicleOverviewRead.model_validate(payload)
