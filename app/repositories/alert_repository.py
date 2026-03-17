from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.entities import Alert
from app.repositories.base import Repository


class AlertRepository(Repository[Alert]):
    def __init__(self) -> None:
        super().__init__(Alert)

    def list_recent(self, db: Session, limit: int = 100) -> list[Alert]:
        query = select(Alert).order_by(desc(Alert.created_at)).limit(limit)
        return list(db.scalars(query).all())

    def list_filtered(
        self,
        db: Session,
        *,
        limit: int = 200,
        vehicle_id: int | None = None,
        route_id: int | None = None,
        severity: str | None = None,
        alert_type: str | None = None,
    ) -> list[Alert]:
        query = select(Alert)
        if vehicle_id is not None:
            query = query.where(Alert.vehicle_id == vehicle_id)
        if route_id is not None:
            query = query.where(Alert.route_id == route_id)
        if severity:
            query = query.where(Alert.severity == severity)
        if alert_type:
            query = query.where(Alert.alert_type == alert_type)
        query = query.order_by(desc(Alert.created_at)).limit(limit)
        return list(db.scalars(query).all())
