"""Build a synthetic LoadPlan from a transport's actual stops + products.

Used as a fallback when a transport row doesn't carry a stashed
`load_plan_json` — typically the seeded historical transports and any
transport persisted before /optimize/persist learned to forward the
LoadPlan. The derived plan is a bin-packing approximation: it doesn't
match what the optimizer would have produced (no time-window awareness,
no real stacking model), but it surfaces the actual products being
delivered, grouped into a believable pallet layout. That's enough for
the truck visualization in the UI — anything is better than a mock.

Heuristic: greedy first-fit by unit-equivalent fraction. CASES_PER_PALLET
and BARRELS_PER_PALLET reflect the real-world rule of thumb (a pallet
holds ~30 cases of bottles or ~4 30L barrels). Anything fractional gets
billed against the same fraction.
"""
from __future__ import annotations

from datetime import date as DateType
from typing import Iterable

from models.domain import (
    DeliveryStop,
    LoadPlan,
    Pallet,
    ProductLine,
    ProductUnit,
    TruckType,
)


# Pallet-equivalent units. 30 cases or 4 barrels = 1 pallet, mixed sums
# to fractions until it overflows into the next pallet.
CASES_PER_PALLET = 30.0
BARRELS_PER_PALLET = 4.0

# Hard ceiling on derived pallets per truck. Reflects fleet capacity by
# truck_type — same numbers used elsewhere in the UI.
TRUCK_CAPACITY: dict[TruckType, int] = {
    TruckType.VAN: 3,
    TruckType.TRUCK_6: 6,
    TruckType.TRUCK_8: 8,
}


def _pallet_fraction(product: ProductLine) -> float:
    """How much of a pallet this product line consumes."""
    if product.unit == ProductUnit.BRL:
        return product.quantity / BARRELS_PER_PALLET
    return product.quantity / CASES_PER_PALLET


def _summary_line(product: ProductLine) -> str:
    return f"{product.quantity} {product.unit.value} · {product.description}"


def _build_pallet(
    index: int,
    products: list[ProductLine],
    stop_ids: Iterable[str],
) -> Pallet:
    return Pallet(
        pallet_index=index,
        pallet_id=f"PAL-{index + 1:03d}",
        stop_ids=sorted(set(stop_ids)),
        is_returnables=False,
        items=[],
        products=products,
        products_summary=[_summary_line(p) for p in products],
    )


def derive_load_plan(
    *,
    transport_id: str,
    truck_type: TruckType,
    transport_date: DateType,
    stops: list[DeliveryStop],
) -> LoadPlan:
    """Pack the transport's products into virtual pallets.

    Walk stops in delivery order, accumulating product lines into the
    current pallet until adding one more would exceed pallet capacity
    (in unit-equivalent fractions). When that happens, close the pallet
    and start a new one. A single stop's products may span multiple
    pallets when the demand is large; a single pallet can also pool
    products from consecutive small stops.
    """
    pallets: list[Pallet] = []
    cur_products: list[ProductLine] = []
    cur_stop_ids: list[str] = []
    cur_used = 0.0

    def flush() -> None:
        nonlocal cur_products, cur_stop_ids, cur_used
        if not cur_products:
            return
        pallets.append(_build_pallet(len(pallets), cur_products, cur_stop_ids))
        cur_products = []
        cur_stop_ids = []
        cur_used = 0.0

    for stop in stops:
        for product in stop.products:
            frac = _pallet_fraction(product)
            if cur_used + frac > 1.0 and cur_products:
                flush()
            cur_products.append(product)
            cur_stop_ids.append(stop.stop_id)
            cur_used += frac
    flush()

    capacity = TRUCK_CAPACITY.get(truck_type, 6)
    if len(pallets) > capacity:
        # Truck doesn't fit everything — keep the first N pallets so the viz
        # still shows what's loaded, even if not the full demand.
        pallets = pallets[:capacity]

    return LoadPlan(
        transport_id=transport_id,
        truck_type=truck_type,
        date=transport_date,
        pallets=pallets,
        pallet_slots_used=len(pallets),
        pallet_slots_total=capacity,
    )
