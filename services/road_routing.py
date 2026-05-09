from __future__ import annotations

from typing import Any

import httpx

from models.domain import DeliveryStop
from services.optimization import DEPOT_LAT, DEPOT_LNG, Matrix


OSRM_BASE_URL = "https://router.project-osrm.org"


def _coordinate_string(coords: list[tuple[float, float]]) -> str:
    return ";".join(f"{lng},{lat}" for lat, lng in coords)


def _has_all_coordinates(stops: list[DeliveryStop]) -> bool:
    return all(stop.lat is not None and stop.lng is not None for stop in stops)


async def build_road_matrix(stops: list[DeliveryStop], timeout_s: float = 8.0) -> Matrix | None:
    if not _has_all_coordinates(stops):
        return None

    coords = [(DEPOT_LAT, DEPOT_LNG)] + [(float(stop.lat), float(stop.lng)) for stop in stops]
    url = f"{OSRM_BASE_URL}/table/v1/driving/{_coordinate_string(coords)}"
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.get(
                url,
                params={"annotations": "distance,duration"},
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        return None

    distances = payload.get("distances")
    durations = payload.get("durations")
    if not _valid_matrix(distances) or not _valid_matrix(durations):
        return None

    return Matrix(
        distance_km=[
            [round(float(distance or 0.0) / 1000.0, 3) for distance in row]
            for row in distances
        ],
        time_min=[
            [max(0, int(round(float(duration or 0.0) / 60.0))) for duration in row]
            for row in durations
        ],
    )


async def build_route_geojson(
    stops: list[DeliveryStop],
    route_indices: list[int],
    timeout_s: float = 8.0,
) -> dict[str, Any] | None:
    if not _has_all_coordinates(stops):
        return None

    all_coords = [(DEPOT_LAT, DEPOT_LNG)] + [(float(stop.lat), float(stop.lng)) for stop in stops]
    ordered_coords = [all_coords[index] for index in route_indices]
    url = f"{OSRM_BASE_URL}/route/v1/driving/{_coordinate_string(ordered_coords)}"
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.get(
                url,
                params={"overview": "full", "geometries": "geojson", "steps": "false"},
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        return None

    routes = payload.get("routes") or []
    geometry = routes[0].get("geometry") if routes else None
    if not geometry:
        return None
    return {
        "type": "Feature",
        "properties": {"source": "osrm", "includes_depot_return": True},
        "geometry": geometry,
    }


def _valid_matrix(value: Any) -> bool:
    return (
        isinstance(value, list)
        and all(isinstance(row, list) for row in value)
        and len(value) > 0
        and all(len(row) == len(value) for row in value)
    )
