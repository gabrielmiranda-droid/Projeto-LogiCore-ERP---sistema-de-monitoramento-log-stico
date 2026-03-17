from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.entities import Alert, Order, Route, TelemetryEvent, Vehicle
from app.models.enums import AlertType, OrderStatus
from app.schemas.telemetry import TelemetryIn
from app.utils.geo import deserialize_points, min_distance_to_route, route_progress_index
from app.utils.geo import distance_km


logger = get_logger(__name__)

MIN_PERSIST_SECONDS = 15
MIN_PERSIST_DISTANCE_KM = 0.25


@dataclass
class TelemetryIngestResult:
    event: TelemetryEvent
    persisted: bool
    alert_count: int


class TelemetryService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def ingest(self, db: Session, payload: TelemetryIn) -> TelemetryIngestResult:
        vehicle = db.get(Vehicle, payload.vehicle_id)
        if not vehicle:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Veiculo nao encontrado")

        route = db.get(Route, payload.route_id)
        if not route:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rota nao encontrada")

        vehicle.route_id = route.id
        if payload.speed_kmh > 0:
            vehicle.status = "EM_MOVIMENTO"
        else:
            vehicle.status = "PARADO"

        latest_event = db.scalar(
            select(TelemetryEvent)
            .where(TelemetryEvent.vehicle_id == payload.vehicle_id)
            .order_by(desc(TelemetryEvent.timestamp))
            .limit(1)
        )
        should_persist = self._should_persist(payload, latest_event)
        event = TelemetryEvent(**payload.model_dump())
        alerts: list[Alert] = []
        if should_persist:
            db.add(event)
            db.flush()
            alerts = self._evaluate_alerts(db, event, route)
        db.commit()
        logger.info(
            "telemetry_ingested",
            extra={
                "context": {
                    "vehicle_id": event.vehicle_id,
                    "alerts": len(alerts),
                    "event_id": event.id if should_persist else None,
                    "persisted": should_persist,
                }
            },
        )
        return TelemetryIngestResult(event=event, persisted=should_persist, alert_count=len(alerts))

    def _evaluate_alerts(self, db: Session, event: TelemetryEvent, route: Route) -> list[Alert]:
        route_points = deserialize_points(route.path_points_json)
        current = (event.latitude, event.longitude)
        alerts: list[Alert] = []

        deviation_km = min_distance_to_route(current, route_points)
        if deviation_km > self.settings.geofence_tolerance_km:
            alerts.append(self._make_alert(db, event, AlertType.ROUTE_DEVIATION, "ALTA", f"Veiculo fora da rota em {deviation_km:.2f} km"))

        if event.speed_kmh > self.settings.speed_limit_kmh:
            alerts.append(self._make_alert(db, event, AlertType.OVERSPEED, "MEDIA", "Velocidade acima do limite operacional"))

        if event.fuel_level <= self.settings.critical_fuel_level:
            alerts.append(self._make_alert(db, event, AlertType.LOW_FUEL, "ALTA", "Nivel de combustivel em faixa critica"))

        active_order = self._find_active_order(db, event.vehicle_id)
        if active_order and active_order.expected_delivery_at:
            progress = route_progress_index(current, route_points)
            progress_ratio = (progress + 1) / max(len(route_points), 1)
            expected_elapsed_minutes = route.expected_duration_minutes * progress_ratio
            actual_elapsed_minutes = (
                (
                    self._normalize_datetime(event.timestamp)
                    - self._normalize_datetime(active_order.shipped_at)
                ).total_seconds()
                / 60
                if active_order.shipped_at
                else 0
            )
            if actual_elapsed_minutes - expected_elapsed_minutes > self.settings.alert_delay_minutes:
                alerts.append(self._make_alert(db, event, AlertType.DELIVERY_DELAY, "MEDIA", "Pedido com atraso previsto"))

        return alerts

    def _find_active_order(self, db: Session, vehicle_id: int) -> Order | None:
        query = (
            select(Order)
            .where(Order.vehicle_id == vehicle_id, Order.status == OrderStatus.IN_ROUTE)
            .order_by(desc(Order.shipped_at))
            .limit(1)
        )
        return db.scalar(query)

    def _make_alert(
        self,
        db: Session,
        event: TelemetryEvent,
        alert_type: AlertType,
        severity: str,
        message: str,
    ) -> Alert:
        alert = Alert(
            vehicle_id=event.vehicle_id,
            route_id=event.route_id,
            telemetry_event_id=event.id,
            alert_type=alert_type,
            severity=severity,
            message=message,
        )
        db.add(alert)
        return alert

    def vehicle_history(self, db: Session, vehicle_id: int) -> list[TelemetryEvent]:
        query = (
            select(TelemetryEvent)
            .where(TelemetryEvent.vehicle_id == vehicle_id)
            .order_by(desc(TelemetryEvent.timestamp))
            .limit(200)
        )
        return list(db.scalars(query).all())

    def _normalize_datetime(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _should_persist(self, payload: TelemetryIn, latest_event: TelemetryEvent | None) -> bool:
        if latest_event is None:
            return True
        elapsed_seconds = (
            self._normalize_datetime(payload.timestamp) - self._normalize_datetime(latest_event.timestamp)
        ).total_seconds()
        moved_km = distance_km(
            (payload.latitude, payload.longitude),
            (latest_event.latitude, latest_event.longitude),
        )
        if elapsed_seconds >= MIN_PERSIST_SECONDS:
            return True
        if moved_km >= MIN_PERSIST_DISTANCE_KM:
            return True
        if payload.speed_kmh > self.settings.speed_limit_kmh:
            return True
        if payload.fuel_level <= self.settings.critical_fuel_level:
            return True
        return False
