from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "damm-smart-truck-api/0.1"


@dataclass(frozen=True)
class Coordinates:
    lat: float
    lng: float


def build_location_query(row: dict[str, Any]) -> str | None:
    parts = [
        row.get("address"),
        row.get("postal_code"),
        row.get("city"),
        "Spain",
    ]
    query = ", ".join(str(part).strip() for part in parts if part)
    return query or None


async def geocode_location(row: dict[str, Any], timeout_s: float = 5.0) -> Coordinates | None:
    query = build_location_query(row)
    if query is None:
        return None

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.get(
                NOMINATIM_URL,
                params={"q": query, "format": "jsonv2", "limit": 1, "addressdetails": 0},
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
    except httpx.HTTPError:
        return None

    payload = response.json()
    if not payload:
        return None

    first = payload[0]
    try:
        return Coordinates(lat=float(first["lat"]), lng=float(first["lon"]))
    except (KeyError, TypeError, ValueError):
        return None
