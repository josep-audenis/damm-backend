from collections import Counter

from models.domain import ProductUnit
from services.data_loader import DataRepository


def test_loader_parses_real_workbooks() -> None:
    snapshot = DataRepository().load(force_refresh=True)

    assert len(snapshot.transports) == 889
    assert snapshot.delivery_count == 8927
    assert len(snapshot.customers) == 1203
    assert snapshot.material_location_count == 1489


def test_known_transport_is_grouped_into_stops_and_products() -> None:
    snapshot = DataRepository().load()
    transport = snapshot.transports["11515121"]

    assert transport.route_code == "DR0045"
    assert transport.driver_id == "850000"
    assert len(transport.stops) == 32
    assert transport.stops[0].stop_id == "828075878"
    assert len(transport.stops[0].products) == 12
    assert transport.stops[0].products[0].warehouse_location == "AA08A1"


def test_new_source_units_are_preserved() -> None:
    snapshot = DataRepository().load()
    units = Counter(
        product.unit
        for transport in snapshot.transports.values()
        for stop in transport.stops
        for product in stop.products
    )

    for unit in [
        ProductUnit.TB,
        ProductUnit.EST,
        ProductUnit.PQ,
        ProductUnit.TIR,
        ProductUnit.BID,
        ProductUnit.ZPR,
    ]:
        assert units[unit] > 0


def test_time_windows_attach_only_when_source_schedule_matches() -> None:
    snapshot = DataRepository().load()

    scheduled = snapshot.transports["11420330"].stops[0]
    assert scheduled.customer_id == "9100568067"
    assert scheduled.time_window is not None
    assert scheduled.time_window.open.isoformat() == "11:30:00"
    assert scheduled.time_window.close.isoformat() == "16:00:00"

    unscheduled = snapshot.transports["11515121"].stops[0]
    assert unscheduled.time_window is None
