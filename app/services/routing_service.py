from __future__ import annotations

import json
from typing import Any

import requests
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.entities import Route, Vehicle
from app.utils.geo import distance_km, serialize_points


logger = get_logger(__name__)


class RoutingService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._cache: dict[tuple[float, float, float, float], dict[str, Any]] = {}

    def get_route_summary(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
        fallback_points: list[tuple[float, float]] | None = None,
        fallback_duration_s: int | None = None,
    ) -> dict[str, Any]:
        cache_key = (origin[0], origin[1], destination[0], destination[1])
        if cache_key in self._cache:
            return self._cache[cache_key]

        coordinates = self._fetch_osrm_route(origin, destination)
        if coordinates is not None:
            self._cache[cache_key] = coordinates
            return coordinates

        fallback_coordinates = fallback_points or [origin, destination]
        distance_m = int(self._estimate_distance_km(fallback_coordinates) * 1000)
        duration_s = fallback_duration_s or int((distance_m / 1000) / 60 * 3600) if distance_m > 0 else 0
        payload = {
            "coordinates": [[lat, lon] for lat, lon in fallback_coordinates],
            "distance_m": distance_m,
            "duration_s": duration_s,
        }
        self._cache[cache_key] = payload
        return payload

    def _fetch_osrm_route(self, origin: tuple[float, float], destination: tuple[float, float]) -> dict[str, Any] | None:
        coordinates = f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
        params = {"overview": "full", "geometries": "geojson", "steps": "false"}
        url = f"{self.settings.osrm_directions_url}/{coordinates}"
        try:
            response = requests.get(url, params=params, timeout=20)
            response.raise_for_status()
            payload = response.json()
            route = payload["routes"][0]
            return {
                "coordinates": [[float(item[1]), float(item[0])] for item in route["geometry"]["coordinates"]],
                "distance_m": float(route["distance"]),
                "duration_s": float(route["duration"]),
            }
        except Exception as exc:
            logger.warning(
                "routing_service_fallback",
                extra={"context": {"reason": str(exc), "origin": origin, "destination": destination}},
            )
            return None

    def hydrate_route_path(self, db: Session, route: Route, fallback_points: list[tuple[float, float]]) -> Route:
        summary = self.get_route_summary(
            origin=(route.origin_latitude, route.origin_longitude),
            destination=(route.destination_latitude, route.destination_longitude),
            fallback_points=fallback_points,
            fallback_duration_s=route.expected_duration_minutes * 60,
        )
        chosen_points = [(float(point[0]), float(point[1])) for point in summary["coordinates"]]
        route.path_points_json = serialize_points(chosen_points)
        route.estimated_distance_km = round(summary["distance_m"] / 1000, 2)
        route.expected_duration_minutes = max(int(round(summary["duration_s"] / 60)), 1)
        return route

    def get_vehicle_planned_route(self, db: Session, vehicle_id: int) -> dict[str, Any] | None:
        vehicle = db.get(Vehicle, vehicle_id)
        if not vehicle or not vehicle.route_id:
            return None
        route = db.get(Route, vehicle.route_id)
        if route is None:
            return None
        fallback_points = [(point["latitude"], point["longitude"]) for point in json.loads(route.path_points_json)]
        summary = self.get_route_summary(
            origin=(route.origin_latitude, route.origin_longitude),
            destination=(route.destination_latitude, route.destination_longitude),
            fallback_points=fallback_points,
            fallback_duration_s=route.expected_duration_minutes * 60,
        )
        return {
            "vehicle_id": vehicle.id,
            "vehicle_code": vehicle.code,
            "license_plate": vehicle.license_plate,
            "status": vehicle.status,
            "route_id": route.id,
            "route_code": route.code,
            "route_name": route.name,
            "origin_name": route.origin_name,
            "destination_name": route.destination_name,
            "origin": {"latitude": route.origin_latitude, "longitude": route.origin_longitude},
            "destination": {"latitude": route.destination_latitude, "longitude": route.destination_longitude},
            "coordinates": summary["coordinates"],
            "distance_m": summary["distance_m"],
            "duration_s": summary["duration_s"],
        }

    def _estimate_distance_km(self, points: list[tuple[float, float]]) -> float:
        if len(points) < 2:
            return 0.0
        total = 0.0
        for first, second in zip(points, points[1:]):
            total += distance_km(first, second)
        return total


routing_service = RoutingService()
