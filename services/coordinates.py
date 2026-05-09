from __future__ import annotations

import json
import asyncio
import unicodedata
from pathlib import Path

from models.domain import DeliveryStop
from services.database import DB_PATH
from services.geocoding import geocode_location


CITY_CENTROIDS = {
    "MOLLET DEL VALLES": (41.54026, 2.21306),
    "MOLLET DEL VALLÈS": (41.54026, 2.21306),
}


def _normalize(value: object) -> str:
    text = str(value or "").strip().upper()
    text = text.replace("'", " ")
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )


def _postal_key(value: object) -> str:
    text = str(value or "").strip()
    return text.lstrip("0") or text


def _load_customer_coordinate_index(db_path: Path = DB_PATH) -> dict[tuple[str, str, str], tuple[float, float]]:
    if not db_path.exists():
        return {}
    try:
        db = json.loads(db_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    index: dict[tuple[str, str, str], tuple[float, float]] = {}
    for customer in db.get("tables", {}).get("customers", []):
        lat = customer.get("lat")
        lng = customer.get("lng")
        if lat is None or lng is None:
            continue
        try:
            coords = (float(lat), float(lng))
        except (TypeError, ValueError):
            continue
        key = (
            _normalize(customer.get("name")),
            _postal_key(customer.get("postal_code")),
            _normalize(customer.get("city")),
        )
        index[key] = coords
    return index


def _address_parts(value: object) -> tuple[str, int | None]:
    text = _normalize(value)
    tokens = text.split()
    if tokens and tokens[0] in {
        "CALLE",
        "CARRER",
        "C",
        "AVENIDA",
        "AVINGUDA",
        "AV",
        "RONDA",
        "RAMBLA",
        "PLAZA",
        "PLACA",
        "PLAÇA",
    }:
        tokens = tokens[1:]
    while tokens and tokens[0] in {"D", "DE", "DEL", "DELA", "LA", "EL"}:
        tokens = tokens[1:]
    number = None
    street_tokens: list[str] = []
    for token in tokens:
        digits = "".join(char for char in token if char.isdigit())
        if digits and number is None:
            number = int(digits)
            continue
        street_tokens.append(token)
    return " ".join(street_tokens), number


def _load_street_coordinate_index(
    db_path: Path = DB_PATH,
) -> dict[tuple[str, str], list[tuple[int | None, float, float]]]:
    if not db_path.exists():
        return {}
    try:
        db = json.loads(db_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    index: dict[tuple[str, str], list[tuple[int | None, float, float]]] = {}
    for customer in db.get("tables", {}).get("customers", []):
        lat = customer.get("lat")
        lng = customer.get("lng")
        if lat is None or lng is None:
            continue
        street, number = _address_parts(customer.get("address"))
        if not street:
            continue
        try:
            item = (number, float(lat), float(lng))
        except (TypeError, ValueError):
            continue
        index.setdefault((_normalize(customer.get("city")), street), []).append(item)
    return index


def _nearest_street_coordinates(
    street_index: dict[tuple[str, str], list[tuple[int | None, float, float]]],
    stop: DeliveryStop,
) -> tuple[float, float] | None:
    street, number = _address_parts(stop.address)
    candidates = street_index.get((_normalize(stop.city), street), [])
    if not candidates:
        return None
    if number is None:
        _, lat, lng = candidates[0]
        return lat, lng
    _, lat, lng = min(
        candidates,
        key=lambda item: abs((item[0] if item[0] is not None else number) - number),
    )
    return lat, lng


def enrich_stops_from_local_coordinates(stops: list[DeliveryStop]) -> list[DeliveryStop]:
    index = _load_customer_coordinate_index()
    street_index = _load_street_coordinate_index()
    if not index and not street_index:
        return stops

    enriched: list[DeliveryStop] = []
    for stop in stops:
        copy = stop.model_copy(deep=True)
        if copy.lat is None or copy.lng is None:
            coords = index.get(
                (
                    _normalize(copy.customer_name),
                    _postal_key(copy.postal_code),
                    _normalize(copy.city),
                )
            )
            if coords is not None:
                copy.lat, copy.lng = coords
        if copy.lat is None or copy.lng is None:
            coords = _nearest_street_coordinates(street_index, copy)
            if coords is not None:
                copy.lat, copy.lng = coords
        if copy.lat is None or copy.lng is None:
            coords = CITY_CENTROIDS.get(_normalize(copy.city))
            if coords is not None:
                copy.lat, copy.lng = coords
        enriched.append(copy)
    return enriched


async def enrich_stops_with_geocoding(stops: list[DeliveryStop]) -> list[DeliveryStop]:
    enriched = enrich_stops_from_local_coordinates(stops)
    output = [stop.model_copy(deep=True) for stop in enriched]

    async def geocode_stop(stop: DeliveryStop) -> DeliveryStop:
        copy = stop.model_copy(deep=True)
        if copy.lat is None or copy.lng is None:
            coordinates = await geocode_location(
                {
                    "name": copy.customer_name,
                    "address": copy.address,
                    "postal_code": copy.postal_code,
                    "city": copy.city,
                },
                timeout_s=3.0,
                use_fallbacks=False,
            )
            if coordinates is not None:
                copy.lat = coordinates.lat
                copy.lng = coordinates.lng
        return copy

    tasks = [geocode_stop(stop) for stop in output]
    try:
        return await asyncio.wait_for(asyncio.gather(*tasks), timeout=6.0)
    except TimeoutError:
        return output
