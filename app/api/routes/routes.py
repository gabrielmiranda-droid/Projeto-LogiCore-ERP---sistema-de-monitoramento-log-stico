import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.route_repository import RouteRepository
from app.schemas.route import PlannedVehicleRouteRead, RouteRead
from app.services.routing_service import routing_service


router = APIRouter(prefix="/routes", tags=["Routes"])
repository = RouteRepository()


def _serialize_route(route) -> RouteRead:
    payload = {
        "id": route.id,
        "created_at": route.created_at,
        "updated_at": route.updated_at,
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
    return RouteRead.model_validate(payload)


@router.get("", response_model=list[RouteRead])
def list_routes(db: Session = Depends(get_db)) -> list[RouteRead]:
    routes = repository.list_all(db)
    return [_serialize_route(route) for route in routes]


@router.get("/{route_id}", response_model=RouteRead)
def get_route(route_id: int, db: Session = Depends(get_db)) -> RouteRead:
    route = repository.get(db, route_id)
    if not route:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rota nao encontrada")
    return _serialize_route(route)


@router.get("/vehicles/{vehicle_id}/planned", response_model=PlannedVehicleRouteRead)
def get_vehicle_planned_route(vehicle_id: int, db: Session = Depends(get_db)) -> PlannedVehicleRouteRead:
    route_payload = routing_service.get_vehicle_planned_route(db, vehicle_id)
    if route_payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Veiculo ou rota nao encontrados")
    return PlannedVehicleRouteRead.model_validate(route_payload)
