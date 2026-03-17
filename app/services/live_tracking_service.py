from __future__ import annotations

import asyncio
import json
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.entities import Alert, Route, TelemetryEvent, Vehicle


@dataclass
class VehicleLiveState:
    vehicle: dict
    route: dict | None
    position: dict | None
    history: deque[dict] = field(default_factory=lambda: deque(maxlen=180))
    active_alerts: list[dict] = field(default_factory=list)
    last_persisted_event_id: int | None = None


class LiveTrackingManager:
    def __init__(self) -> None:
        self.subscribers: dict[int, set[asyncio.Queue]] = {}

    def subscribe(self, vehicle_id: int) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=4)
        self.subscribers.setdefault(vehicle_id, set()).add(queue)
        return queue

    def unsubscribe(self, vehicle_id: int, queue: asyncio.Queue) -> None:
        if vehicle_id in self.subscribers:
            self.subscribers[vehicle_id].discard(queue)
            if not self.subscribers[vehicle_id]:
                del self.subscribers[vehicle_id]

    async def broadcast(self, vehicle_id: int, payload: dict) -> None:
        for queue in list(self.subscribers.get(vehicle_id, set())):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            await queue.put(payload)


live_tracking_manager = LiveTrackingManager()


class LiveTrackingService:
    def __init__(self) -> None:
        self.state_cache: dict[int, VehicleLiveState] = {}

    def _serialize_vehicle(self, vehicle: Vehicle) -> dict:
        return {
            "id": vehicle.id,
            "code": vehicle.code,
            "license_plate": vehicle.license_plate,
            "model": vehicle.model,
            "status": vehicle.status,
            "route_id": vehicle.route_id,
        }

    def _serialize_route(self, route: Route | None) -> dict | None:
        if route is None:
            return None
        return {
            "id": route.id,
            "code": route.code,
            "name": route.name,
            "origin_name": route.origin_name,
            "destination_name": route.destination_name,
            "origin_latitude": route.origin_latitude,
            "origin_longitude": route.origin_longitude,
            "destination_latitude": route.destination_latitude,
            "destination_longitude": route.destination_longitude,
            "estimated_distance_km": route.estimated_distance_km,
            "expected_duration_minutes": route.expected_duration_minutes,
            "path_points": json.loads(route.path_points_json),
        }

    def _serialize_position(
        self,
        *,
        latitude: float,
        longitude: float,
        speed_kmh: float,
        fuel_level: float,
        cargo_occupancy: float,
        timestamp: datetime,
        event_id: int | None = None,
    ) -> dict:
        payload = {
            "latitude": latitude,
            "longitude": longitude,
            "speed_kmh": speed_kmh,
            "fuel_level": fuel_level,
            "cargo_occupancy": cargo_occupancy,
            "timestamp": timestamp.isoformat(),
        }
        if event_id is not None:
            payload["id"] = event_id
        return payload

    def _serialize_active_alerts(self, db: Session, vehicle_id: int) -> list[dict]:
        rows = db.execute(
            select(
                Alert.id,
                Alert.alert_type,
                Alert.severity,
                Alert.message,
                Alert.created_at,
                TelemetryEvent.latitude,
                TelemetryEvent.longitude,
                TelemetryEvent.timestamp,
            )
            .join(TelemetryEvent, TelemetryEvent.id == Alert.telemetry_event_id)
            .where(Alert.vehicle_id == vehicle_id, Alert.resolved.is_(False))
            .order_by(desc(Alert.created_at))
            .limit(6)
        ).all()
        return [
            {
                "id": row.id,
                "alert_type": getattr(row.alert_type, "value", str(row.alert_type)),
                "severity": row.severity,
                "message": row.message,
                "created_at": row.created_at.isoformat(),
                "latitude": row.latitude,
                "longitude": row.longitude,
                "timestamp": row.timestamp.isoformat(),
            }
            for row in rows
        ]

    def upsert_state(
        self,
        *,
        vehicle: Vehicle,
        route: Route | None,
        position: dict,
        active_alerts: list[dict] | None = None,
        persisted_event_id: int | None = None,
    ) -> dict:
        state = self.state_cache.get(vehicle.id)
        if state is None:
            state = VehicleLiveState(
                vehicle=self._serialize_vehicle(vehicle),
                route=self._serialize_route(route),
                position=position,
            )
            self.state_cache[vehicle.id] = state
        else:
            state.vehicle = self._serialize_vehicle(vehicle)
            state.route = self._serialize_route(route)
            state.position = position

        state.history.append(position)
        if active_alerts is not None:
            state.active_alerts = active_alerts[:6]
        if persisted_event_id is not None:
            state.last_persisted_event_id = persisted_event_id

        return {
            "message_type": "update",
            "vehicle": state.vehicle,
            "position": state.position,
            "active_alerts": state.active_alerts,
        }

    def build_vehicle_payload(self, db: Session, vehicle_id: int) -> dict | None:
        cached_state = self.state_cache.get(vehicle_id)
        if cached_state is not None:
            return {
                "message_type": "bootstrap",
                "vehicle": cached_state.vehicle,
                "position": cached_state.position,
                "route": cached_state.route,
                "history": list(cached_state.history),
                "active_alerts": cached_state.active_alerts,
            }

        vehicle = db.get(Vehicle, vehicle_id)
        if not vehicle:
            return None

        latest_event = db.scalar(
            select(TelemetryEvent)
            .where(TelemetryEvent.vehicle_id == vehicle_id)
            .order_by(desc(TelemetryEvent.timestamp))
            .limit(1)
        )
        route = db.get(Route, vehicle.route_id) if vehicle.route_id else None
        history = list(
            db.scalars(
                select(TelemetryEvent)
                .where(TelemetryEvent.vehicle_id == vehicle_id)
                .order_by(TelemetryEvent.timestamp.asc())
                .limit(120)
            ).all()
        )
        active_alerts = self._serialize_active_alerts(db, vehicle_id)

        position = None
        if latest_event is not None:
            position = self._serialize_position(
                latitude=latest_event.latitude,
                longitude=latest_event.longitude,
                speed_kmh=latest_event.speed_kmh,
                fuel_level=latest_event.fuel_level,
                cargo_occupancy=latest_event.cargo_occupancy,
                timestamp=latest_event.timestamp,
                event_id=latest_event.id,
            )

        state = VehicleLiveState(
            vehicle=self._serialize_vehicle(vehicle),
            route=self._serialize_route(route),
            position=position,
            history=deque(
                [
                    self._serialize_position(
                        latitude=event.latitude,
                        longitude=event.longitude,
                        speed_kmh=event.speed_kmh,
                        fuel_level=event.fuel_level,
                        cargo_occupancy=event.cargo_occupancy,
                        timestamp=event.timestamp,
                        event_id=event.id,
                    )
                    for event in history
                ],
                maxlen=180,
            ),
            active_alerts=active_alerts,
            last_persisted_event_id=latest_event.id if latest_event is not None else None,
        )
        self.state_cache[vehicle_id] = state

        return {
            "message_type": "bootstrap",
            "vehicle": state.vehicle,
            "position": state.position,
            "route": state.route,
            "history": list(state.history),
            "active_alerts": state.active_alerts,
        }


live_tracking_service = LiveTrackingService()
