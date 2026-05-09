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


def _clean_part(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_spanish_postal_code(value: Any) -> str | None:
    text = _clean_part(value)
    if text is None:
        return None
    if text.endswith(".0"):
        text = text[:-2]
    if text.isdigit() and len(text) < 5:
        return text.zfill(5)
    return text


def build_location_query(row: dict[str, Any]) -> str | None:
    queries = build_location_queries(row)
    return queries[0] if queries else None


def build_location_queries(row: dict[str, Any]) -> list[str]:
    primary_location = _clean_part(row.get("address")) or _clean_part(row.get("name"))
    postal_code = _normalize_spanish_postal_code(row.get("postal_code"))
    city = _clean_part(row.get("city"))
    parts = [
        primary_location,
        postal_code,
        city,
        "Spain",
    ]
    query = ", ".join(part for part in parts if part)
    queries = [query] if query else []

    name = _clean_part(row.get("name"))
    if name and name.upper().startswith("DDI ") and city:
        queries.append(f"Damm {city}, Spain")

    fallback_parts = [postal_code, city, "Spain"]
    fallback_query = ", ".join(part for part in fallback_parts if part)
    if fallback_query and fallback_query not in queries:
        queries.append(fallback_query)

    return queries


def _coordinates_from_payload(payload: list[dict[str, Any]]) -> Coordinates | None:
    if not payload:
        return None

    first = payload[0]
    try:
        coordinates = Coordinates(lat=float(first["lat"]), lng=float(first["lon"]))
    except (KeyError, TypeError, ValueError):
        return None

    if not (-90 <= coordinates.lat <= 90 and -180 <= coordinates.lng <= 180):
        return None
    return coordinates


async def geocode_location(row: dict[str, Any], timeout_s: float = 5.0) -> Coordinates | None:
    queries = build_location_queries(row)
    if not queries:
        return None

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            for query in queries:
                response = await client.get(
                    NOMINATIM_URL,
                    params={"q": query, "format": "jsonv2", "limit": 1, "addressdetails": 0},
                    headers={"User-Agent": USER_AGENT},
                )
                response.raise_for_status()
                coordinates = _coordinates_from_payload(response.json())
                if coordinates is not None:
                    return coordinates
    except httpx.HTTPError:
        return None

    return None
