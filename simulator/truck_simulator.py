from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import sin
from pathlib import Path

import requests

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import get_settings
from app.utils.geo import distance_km


API_BASE_URL = os.getenv("LOGICORE_API_URL", "http://localhost:8000/api").rstrip("/")
TELEMETRY_URL = f"{API_BASE_URL}/telemetry"
DENSIFY_STEP_KM = 0.08


@dataclass
class SimulatedVehicle:
    vehicle_id: int
    route_id: int
    base_speed_kmh: float
    fuel_level: float
    occupancy: float
    path_points: list[tuple[float, float]]
    path_cursor: int = 0
    distance_into_segment_km: float = 0.0
    tick_count: int = 0
    current_position: tuple[float, float] | None = None
    current_speed_kmh: float = 0.0


def load_route_points(session: requests.Session, route_id: int) -> list[tuple[float, float]]:
    response = session.get(f"{API_BASE_URL}/routes/{route_id}", timeout=10)
    response.raise_for_status()
    payload = response.json()
    raw_points = [(float(point["latitude"]), float(point["longitude"])) for point in payload["path_points"]]
    return densify_path(raw_points)


def interpolate_point(start: tuple[float, float], end: tuple[float, float], ratio: float) -> tuple[float, float]:
    return (
        start[0] + (end[0] - start[0]) * ratio,
        start[1] + (end[1] - start[1]) * ratio,
    )


def densify_path(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(points) < 2:
        return points
    dense_points: list[tuple[float, float]] = [points[0]]
    for start, end in zip(points, points[1:]):
        segment_distance = distance_km(start, end)
        steps = max(int(segment_distance / DENSIFY_STEP_KM), 1)
        for idx in range(1, steps + 1):
            dense_points.append(interpolate_point(start, end, idx / steps))
    return dense_points


def build_fleet(session: requests.Session) -> list[SimulatedVehicle]:
    return [
        SimulatedVehicle(
            vehicle_id=1,
            route_id=1,
            base_speed_kmh=72,
            fuel_level=88,
            occupancy=76,
            path_points=load_route_points(session, 1),
        ),
        SimulatedVehicle(
            vehicle_id=2,
            route_id=2,
            base_speed_kmh=66,
            fuel_level=72,
            occupancy=64,
            path_points=load_route_points(session, 2),
        ),
    ]


def current_segment(vehicle: SimulatedVehicle) -> tuple[tuple[float, float], tuple[float, float]]:
    if vehicle.path_cursor >= len(vehicle.path_points) - 1:
        vehicle.path_cursor = 0
        vehicle.distance_into_segment_km = 0.0
    return vehicle.path_points[vehicle.path_cursor], vehicle.path_points[vehicle.path_cursor + 1]


def compute_speed(vehicle: SimulatedVehicle) -> float:
    wave_adjustment = sin(vehicle.tick_count / 5) * 6
    stop_modifier = 0.0
    if vehicle.tick_count % 31 == 0:
        stop_modifier = -vehicle.base_speed_kmh * 0.75
    elif vehicle.tick_count % 17 == 0:
        stop_modifier = -18
    speed = vehicle.base_speed_kmh + wave_adjustment + stop_modifier
    return round(max(speed, 8.0), 2)


def advance_vehicle(vehicle: SimulatedVehicle, interval_seconds: int) -> dict:
    vehicle.tick_count += 1
    vehicle.current_speed_kmh = compute_speed(vehicle)
    travel_km = vehicle.current_speed_kmh * (interval_seconds / 3600)

    while travel_km > 0:
        start, end = current_segment(vehicle)
        segment_distance = max(distance_km(start, end), 0.001)
        remaining_segment = segment_distance - vehicle.distance_into_segment_km
        if travel_km >= remaining_segment:
            travel_km -= remaining_segment
            vehicle.path_cursor += 1
            vehicle.distance_into_segment_km = 0.0
            vehicle.current_position = end
        else:
            vehicle.distance_into_segment_km += travel_km
            ratio = vehicle.distance_into_segment_km / segment_distance
            vehicle.current_position = interpolate_point(start, end, ratio)
            travel_km = 0

    if vehicle.current_position is None:
        vehicle.current_position = vehicle.path_points[0]

    vehicle.fuel_level = max(vehicle.fuel_level - (vehicle.current_speed_kmh / 600), 9)
    vehicle.occupancy = max(vehicle.occupancy - 0.03, 18)

    latitude, longitude = vehicle.current_position
    return {
        "vehicle_id": vehicle.vehicle_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "latitude": round(latitude, 6),
        "longitude": round(longitude, 6),
        "speed_kmh": vehicle.current_speed_kmh,
        "fuel_level": round(vehicle.fuel_level, 2),
        "cargo_occupancy": round(vehicle.occupancy, 2),
        "route_id": vehicle.route_id,
    }


def main() -> None:
    settings = get_settings()
    session = requests.Session()
    fleet = build_fleet(session)
    interval_seconds = max(int(settings.simulator_interval_seconds), 1)
    while True:
        started_at = time.perf_counter()
        for vehicle in fleet:
            payload = advance_vehicle(vehicle, interval_seconds)
            response = session.post(TELEMETRY_URL, json=payload, timeout=10)
            print(
                f"[{datetime.now():%H:%M:%S}] "
                f"vehicle={vehicle.vehicle_id} route={vehicle.route_id} "
                f"speed={payload['speed_kmh']:.1f}km/h fuel={payload['fuel_level']:.1f}% "
                f"status={response.status_code}"
            )
        elapsed = time.perf_counter() - started_at
        time.sleep(max(interval_seconds - elapsed, 0.1))


if __name__ == "__main__":
    main()
