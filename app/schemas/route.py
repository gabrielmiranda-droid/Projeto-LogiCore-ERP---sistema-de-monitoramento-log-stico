from app.schemas.common import ORMModel, TimestampedSchema


class RouteRead(TimestampedSchema):
    code: str
    name: str
    origin_name: str
    destination_name: str
    origin_latitude: float
    origin_longitude: float
    destination_latitude: float
    destination_longitude: float
    estimated_distance_km: float
    expected_duration_minutes: int
    path_points: list[dict[str, float]]


class PlannedVehicleRouteRead(ORMModel):
    vehicle_id: int
    vehicle_code: str
    license_plate: str
    status: str
    route_id: int
    route_code: str
    route_name: str
    origin_name: str
    destination_name: str
    origin: dict[str, float]
    destination: dict[str, float]
    coordinates: list[list[float]]
    distance_m: float
    duration_s: float
