from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Alert, Order, Route, TelemetryEvent, Vehicle
from app.schemas.kpi import KPIRead
from app.services.kpi_service import KPIService


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
service = KPIService()


@router.get("/kpis", response_model=KPIRead)
def get_kpis(db: Session = Depends(get_db)) -> KPIRead:
    return service.get_operational_kpis(db)


@router.get("/snapshot")
def get_snapshot(db: Session = Depends(get_db)) -> dict:
    latest_events_subquery = (
        select(
            TelemetryEvent.vehicle_id,
            func.max(TelemetryEvent.timestamp).label("last_timestamp"),
        )
        .group_by(TelemetryEvent.vehicle_id)
        .subquery()
    )

    vehicles = db.execute(
        select(
            Vehicle.id,
            Vehicle.code,
            Vehicle.license_plate,
            Vehicle.model,
            Vehicle.status.label("vehicle_status"),
            Vehicle.route_id,
            Route.code.label("route_code"),
            Route.name.label("route_name"),
            TelemetryEvent.latitude,
            TelemetryEvent.longitude,
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

    order_counts = db.execute(
        select(Order.status, func.count(Order.id).label("count")).group_by(Order.status)
    ).all()
    avg_delivery = db.scalar(
        select(func.avg((func.julianday(Order.delivered_at) - func.julianday(Order.shipped_at)) * 24))
        .where(Order.delivered_at.is_not(None), Order.shipped_at.is_not(None))
    )
    alert_rows = db.execute(
        select(Alert.id, Alert.alert_type, Alert.severity, Alert.message, Alert.vehicle_id, Alert.created_at)
        .order_by(Alert.created_at.desc())
        .limit(20)
    ).mappings()

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "kpis": service.get_operational_kpis(db).model_dump(),
        "vehicles": [dict(row) for row in vehicles],
        "alerts": [dict(row) for row in alert_rows],
        "orders_by_status": {getattr(status, "value", str(status)): count for status, count in order_counts},
        "average_delivery_hours": round(float(avg_delivery or 0), 2),
    }
