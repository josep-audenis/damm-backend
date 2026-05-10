"""Persist a precomputed RouteResult (e.g. one returned by /preview) as a
real transport + delivery_stops in the JSON DB. Does NOT re-run the solver.

This exists so the frontend can call the optimizer in preview mode (cheap, no
side-effects), let the user pick a suggestion, and then commit it cleanly.
"""
from __future__ import annotations

from datetime import date as DateType

from models.domain import LoadPlan, RouteResult, TruckType
from services.database import db_service
from services.driver_assignment import pick_driver_for_route


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


DEFAULT_START_HHMM = "09:00"
SCHEDULE_BUFFER_MIN = 15
DEFAULT_DURATION_MIN = 60


def _hhmm_to_min(value: str | None) -> int | None:
    if not value or len(value) < 4:
        return None
    try:
        h, m = value.split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def _min_to_hhmm(total_min: int) -> str:
    total = max(0, total_min) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def _compute_start_time(
    db: dict,
    *,
    driver_id: str | None,
    transport_date: DateType,
) -> str:
    """Earliest non-overlapping start for this route on the driver's day.
    Default 09:00; if the driver already has transports today, slot in
    after the latest one ends + buffer."""
    if not driver_id:
        return DEFAULT_START_HHMM

    iso_date = transport_date.isoformat()
    latest_end_min = 0
    for t in db["tables"].get("transports", []):
        if t.get("driver_id") != driver_id:
            continue
        if t.get("transport_date") != iso_date:
            continue
        start_min = _hhmm_to_min(t.get("start_time"))
        if start_min is None:
            continue
        duration = int(t.get("duration_min") or DEFAULT_DURATION_MIN)
        end_min = start_min + duration
        if end_min > latest_end_min:
            latest_end_min = end_min

    if latest_end_min == 0:
        return DEFAULT_START_HHMM
    return _min_to_hhmm(latest_end_min + SCHEDULE_BUFFER_MIN)


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
    load: LoadPlan | None = None,
) -> dict[str, str | int | None]:
    """Insert the route as a transport row + one delivery_stops row per stop.

    delivery_lines (the stop -> order linkage) are not created here — preview
    routes don't carry an order_id per stop, so the connection would have to
    be re-derived. Stops are still queryable via /api/v1/data/transport/{id}
    and the customer linkage is preserved via delivery_stops.customer_id.

    When `load` is provided (the LoadPlan that came back alongside the route
    in /optimize/full/preview), it's stashed on the transport row as
    `load_plan_json` so the truck visualization can be reconstructed later
    without re-running the solver.
    """
    db = db_service.load()

    driver_id = _resolve_driver_id(
        db,
        candidate_id=route.driver_id or None,
        candidate_name=route.driver_name,
    )
    if driver_id is None:
        # Optimizer doesn't surface a real driver (its driver_name is the
        # truck plate). Pick one from the drivers table based on which of
        # them have historically delivered to this route's zones the most.
        driver_id = pick_driver_for_route(db, route)
    truck_id = _resolve_truck_id(
        db,
        candidate_id=route.vehicle_id,
        truck_type=route.truck_type,
        warehouse_id=warehouse_id,
    )
    route_id = _resolve_route_id(db, route_code=route.route_code)

    duration_min = int(route.total_time_min or DEFAULT_DURATION_MIN)
    start_time = _compute_start_time(
        db,
        driver_id=driver_id,
        transport_date=route.date,
    )

    transport_payload: dict[str, object] = {
        "transport_date": route.date.isoformat(),
        "route_id": route_id,
        "driver_id": driver_id,
        "truck_id": truck_id,
        "start_time": start_time,
        "duration_min": duration_min,
    }
    if load is not None:
        # Pydantic -> dict so json.dumps in db_service can serialize cleanly
        # (handles Decimal, enums, dates inside LoadPlan).
        transport_payload["load_plan_json"] = load.model_dump(mode="json")

    transport = db_service.stage_insert(db, "transports", transport_payload)

    inserted_stops = 0
    for stop in route.ordered_stops:
        # We don't create delivery_lines here (preview routes don't carry an
        # order_id per stop), so the read endpoint can't reconstruct the
        # stop's products by walking delivery_lines -> orders. Stash them
        # directly on the row instead — the repo prefers this over the join
        # when present.
        db_service.stage_insert(
            db,
            "delivery_stops",
            {
                "transport_id": transport["id"],
                "customer_id": stop.customer_id,
                "sequence": stop.sequence,
                "lat": stop.lat,
                "lng": stop.lng,
                "products_json": [
                    p.model_dump(mode="json") for p in stop.products
                ],
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
