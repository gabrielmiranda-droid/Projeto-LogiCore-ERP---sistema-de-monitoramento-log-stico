from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.alert_repository import AlertRepository
from app.schemas.alert import AlertRead


router = APIRouter(prefix="/alerts", tags=["Alerts"])
repository = AlertRepository()


@router.get("", response_model=list[AlertRead])
def list_alerts(
    vehicle_id: int | None = None,
    route_id: int | None = None,
    severity: str | None = None,
    alert_type: str | None = None,
    db: Session = Depends(get_db),
) -> list[AlertRead]:
    alerts = repository.list_filtered(
        db,
        vehicle_id=vehicle_id,
        route_id=route_id,
        severity=severity,
        alert_type=alert_type,
    )
    return [AlertRead.model_validate(alert) for alert in alerts]
