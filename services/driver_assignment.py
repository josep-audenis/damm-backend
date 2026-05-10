"""Pick a real driver for a freshly-optimized route based on how often each
driver has historically delivered to the route's zones.

Why this exists: the optimizer doesn't know about the `drivers` table —
its `RouteResult.driver_name` is actually the truck plate. Without this
post-hoc match, every persisted route would land with `driver_id = None`
and show "—" everywhere.

Heuristic: for each driver, count how many historical deliveries they
made to each zone_code. Score a candidate driver against a new route by
summing their visits to that route's zones. Highest score wins. When
nobody has any history in any of the route's zones (rare — happens for
brand-new zone_codes), fall back to the most-experienced driver overall
so a route always gets *someone*.
"""
from __future__ import annotations

from typing import Any

from models.domain import RouteResult


def pick_driver_for_route(
    db: dict[str, Any],
    route: RouteResult,
) -> str | None:
    """Return the driver_id best suited for `route`, or None if there are
    no drivers at all in the DB."""
    drivers = db["tables"].get("drivers") or []
    if not drivers:
        return None

    familiarity = driver_zone_familiarity(db)
    route_zones = _route_zones(db, route)

    # Score each driver by total visits to any of the route's zones.
    def score(driver_id: str) -> int:
        zone_counts = familiarity.get(driver_id, {})
        return sum(zone_counts.get(z, 0) for z in route_zones)

    scored = [(d["id"], score(d["id"])) for d in drivers]
    best_id, best_score = max(scored, key=lambda kv: kv[1])

    if best_score > 0:
        return str(best_id)

    # Nobody has touched these zones — fall back to the most-experienced
    # driver (most total historical visits). Keeps the slot from staying
    # empty for novel zones.
    most_experienced = max(
        drivers,
        key=lambda d: sum(familiarity.get(d["id"], {}).values()),
    )
    return str(most_experienced["id"])


def driver_zone_familiarity(
    db: dict[str, Any],
) -> dict[str, dict[str, int]]:
    """Walk the historical transports to build
    `{driver_id: {zone_code: visit_count}}`.

    Computed on-demand at persist time. ~50ms over the seeded data; cheap
    enough that caching isn't worth the staleness risk (a freshly persisted
    route updates the driver's familiarity for the next persist call)."""
    customer_zones: dict[str, str] = {}
    for c in db["tables"].get("customers", []):
        zone = c.get("zone_code")
        if zone:
            customer_zones[c["id"]] = str(zone)

    stops_by_transport: dict[str, list[dict[str, Any]]] = {}
    for stop in db["tables"].get("delivery_stops", []):
        tid = stop.get("transport_id")
        if tid:
            stops_by_transport.setdefault(tid, []).append(stop)

    familiarity: dict[str, dict[str, int]] = {}
    for transport in db["tables"].get("transports", []):
        driver_id = transport.get("driver_id")
        if not driver_id:
            continue
        zone_counts = familiarity.setdefault(driver_id, {})
        for stop in stops_by_transport.get(transport["id"], []):
            zone = customer_zones.get(stop.get("customer_id"))
            if zone:
                zone_counts[zone] = zone_counts.get(zone, 0) + 1
    return familiarity


def _route_zones(db: dict[str, Any], route: RouteResult) -> list[str]:
    """The zone_code of every stop on the new route, in delivery order.
    Stops whose customer has no zone are skipped — they don't influence
    the score either way."""
    customer_zones: dict[str, str] = {}
    for c in db["tables"].get("customers", []):
        zone = c.get("zone_code")
        if zone:
            customer_zones[c["id"]] = str(zone)

    return [
        customer_zones[stop.customer_id]
        for stop in route.ordered_stops
        if stop.customer_id in customer_zones
    ]
