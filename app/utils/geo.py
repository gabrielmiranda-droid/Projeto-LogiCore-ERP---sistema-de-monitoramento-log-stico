import json
from collections.abc import Iterable

from geopy.distance import geodesic


def serialize_points(points: Iterable[tuple[float, float]]) -> str:
    return json.dumps([{"latitude": lat, "longitude": lon} for lat, lon in points])


def deserialize_points(raw: str) -> list[tuple[float, float]]:
    data = json.loads(raw)
    return [(item["latitude"], item["longitude"]) for item in data]


def distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    return geodesic(a, b).km


def min_distance_to_route(current: tuple[float, float], route_points: list[tuple[float, float]]) -> float:
    return min(distance_km(current, point) for point in route_points)


def route_progress_index(current: tuple[float, float], route_points: list[tuple[float, float]]) -> int:
    distances = [distance_km(current, point) for point in route_points]
    return distances.index(min(distances))
