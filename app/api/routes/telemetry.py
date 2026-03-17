import anyio
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Route, Vehicle
from app.schemas.telemetry import TelemetryIn, TelemetryRead
from app.services.live_tracking_service import live_tracking_manager, live_tracking_service
from app.services.telemetry_service import TelemetryService


router = APIRouter(prefix="/telemetry", tags=["Telemetry"])
service = TelemetryService()


@router.post("", response_model=TelemetryRead, status_code=201)
def receive_telemetry(payload: TelemetryIn, db: Session = Depends(get_db)) -> TelemetryRead:
    result = service.ingest(db, payload)
    vehicle = db.get(Vehicle, payload.vehicle_id)
    route = db.get(Route, payload.route_id)
    active_alerts = None
    if result.persisted and vehicle is not None:
        active_alerts = live_tracking_service._serialize_active_alerts(db, vehicle.id)
    live_payload = None
    if vehicle is not None:
        live_payload = live_tracking_service.upsert_state(
            vehicle=vehicle,
            route=route,
            position={
                "id": result.event.id,
                "latitude": payload.latitude,
                "longitude": payload.longitude,
                "speed_kmh": payload.speed_kmh,
                "fuel_level": payload.fuel_level,
                "cargo_occupancy": payload.cargo_occupancy,
                "timestamp": payload.timestamp.isoformat(),
            },
            active_alerts=active_alerts,
            persisted_event_id=result.event.id if result.persisted else None,
        )
    if live_payload is not None:
        anyio.from_thread.run(live_tracking_manager.broadcast, payload.vehicle_id, live_payload)
    return TelemetryRead.model_validate(result.event)


@router.get("/vehicles/{vehicle_id}/history", response_model=list[TelemetryRead])
def vehicle_history(vehicle_id: int, db: Session = Depends(get_db)) -> list[TelemetryRead]:
    events = service.vehicle_history(db, vehicle_id)
    return [TelemetryRead.model_validate(event) for event in events]
