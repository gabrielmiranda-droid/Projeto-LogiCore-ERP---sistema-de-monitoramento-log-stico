from app.schemas.common import TimestampedSchema


class AlertRead(TimestampedSchema):
    vehicle_id: int
    route_id: int
    telemetry_event_id: int
    alert_type: str
    severity: str
    message: str
    resolved: bool
