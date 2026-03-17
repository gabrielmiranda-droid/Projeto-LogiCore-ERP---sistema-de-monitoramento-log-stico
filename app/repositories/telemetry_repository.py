from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.entities import TelemetryEvent
from app.repositories.base import Repository


class TelemetryRepository(Repository[TelemetryEvent]):
    def __init__(self) -> None:
        super().__init__(TelemetryEvent)

    def list_vehicle_history(self, db: Session, vehicle_id: int, limit: int = 200) -> list[TelemetryEvent]:
        query = (
            select(TelemetryEvent)
            .where(TelemetryEvent.vehicle_id == vehicle_id)
            .order_by(desc(TelemetryEvent.timestamp))
            .limit(limit)
        )
        return list(db.scalars(query).all())

    def latest_for_vehicle(self, db: Session, vehicle_id: int) -> TelemetryEvent | None:
        query = (
            select(TelemetryEvent)
            .where(TelemetryEvent.vehicle_id == vehicle_id)
            .order_by(desc(TelemetryEvent.timestamp))
            .limit(1)
        )
        return db.scalar(query)
