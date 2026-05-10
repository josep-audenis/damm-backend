"""Persist a precomputed RouteResult (e.g. one returned by /preview) as a
real transport + delivery_stops in the JSON DB. Does NOT re-run the solver.

This exists so the frontend can call the optimizer in preview mode (cheap, no
side-effects), let the user pick a suggestion, and then commit it cleanly.
"""
from __future__ import annotations

from models.domain import RouteResult, TruckType
from services.database import db_service


def _normalize_text(value: str | None) -> str:
    return (value or "").strip().casefold()


def _resolve_driver_id(
    db: dict,
    *,
    candidate_id: str | None,
    candidate_name: str | None,
) -> str | None:
    drivers = db["tables"].get("drivers", [])
    if candidate_id:
        for row in drivers:
            if row.get("id") == candidate_id:
                return candidate_id
    if candidate_name:
        target = _normalize_text(candidate_name)
        for row in drivers:
            if _normalize_text(row.get("name")) == target:
                return str(row.get("id"))
    return None


def _resolve_truck_id(
    db: dict,
    *,
    candidate_id: str | None,
    truck_type: TruckType,
    warehouse_id: str | None,
) -> str | None:
    trucks = db["tables"].get("trucks", [])
    if candidate_id:
        for row in trucks:
            if row.get("id") == candidate_id:
                return candidate_id

    expected_capacity = {
        TruckType.VAN: 3,
        TruckType.TRUCK_6: 6,
        TruckType.TRUCK_8: 8,
    }.get(truck_type, 6)

    matches = [
        row for row in trucks
        if int(row.get("capacity_pallets") or 0) == expected_capacity
    ]
    if warehouse_id:
        scoped = [row for row in matches if row.get("warehouse_id") == warehouse_id]
        if scoped:
            return str(scoped[0]["id"])
    return str(matches[0]["id"]) if matches else None


def _resolve_route_id(db: dict, *, route_code: str) -> str | None:
    """Match the route_code against the routes table; create a row if missing
    so the persisted transport renders with its optimizer label (e.g. "OPT-15")
    instead of an empty string in the UI."""
    if not route_code:
        return None
    target = _normalize_text(route_code)
    for row in db["tables"].get("routes", []):
        if _normalize_text(row.get("code")) == target:
            return str(row.get("id"))
        if _normalize_text(row.get("name")) == target:
            return str(row.get("id"))
    # Create the missing route row so reads can join by route_id.
    new_row = db_service.stage_insert(
        db,
        "routes",
        {"code": route_code, "name": route_code, "zone_code": None},
    )
    return str(new_row["id"])


def persist_route_result(
    route: RouteResult,
    *,
    warehouse_id: str | None = None,
) -> dict[str, str | int | None]:
    """Insert the route as a transport row + one delivery_stops row per stop.

    delivery_lines (the stop -> order linkage) are not created here — preview
    routes don't carry an order_id per stop, so the connection would have to
    be re-derived. Stops are still queryable via /api/v1/data/transport/{id}
    and the customer linkage is preserved via delivery_stops.customer_id.
    """
    db = db_service.load()

    driver_id = _resolve_driver_id(
        db,
        candidate_id=route.driver_id or None,
        candidate_name=route.driver_name,
    )
    truck_id = _resolve_truck_id(
        db,
        candidate_id=route.vehicle_id,
        truck_type=route.truck_type,
        warehouse_id=warehouse_id,
    )
    route_id = _resolve_route_id(db, route_code=route.route_code)

    transport = db_service.stage_insert(
        db,
        "transports",
        {
            "transport_date": route.date.isoformat(),
            "route_id": route_id,
            "driver_id": driver_id,
            "truck_id": truck_id,
        },
    )

    inserted_stops = 0
    for stop in route.ordered_stops:
        db_service.stage_insert(
            db,
            "delivery_stops",
            {
                "transport_id": transport["id"],
                "customer_id": stop.customer_id,
                "sequence": stop.sequence,
                "lat": stop.lat,
                "lng": stop.lng,
            },
        )
        inserted_stops += 1

    db_service.save(db)

    return {
        "transport_id": str(transport["id"]),
        "stops_inserted": inserted_stops,
        "resolved_driver_id": driver_id,
        "resolved_truck_id": truck_id,
        "resolved_route_id": route_id,
    }
