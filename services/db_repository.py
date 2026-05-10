from __future__ import annotations

from datetime import date, time
from typing import Any

from models.domain import (
    DeliveryStop,
    LoadPlan,
    ProductCategory,
    ProductDimensions,
    ProductLine,
    ProductUnit,
    TimeWindow,
    TruckType,
)
from models.schemas import (
    CustomerDetail,
    DriverWithZones,
    DriverZoneStat,
    RouteSummary,
    TransportDetail,
    TransportSummary,
)
from services.database import db_service
from services.driver_assignment import driver_zone_familiarity
from services.load_derivation import derive_load_plan


class DbRepository:
    def _tables(self) -> dict[str, list[dict[str, Any]]]:
        return db_service._load()["tables"]

    def health(self) -> dict[str, Any]:
        tables = self._tables()
        customers = tables["customers"]
        return {
            "data_loaded": bool(customers and tables["transports"]),
            "customer_count": len(customers),
            "transport_count": len(tables["transports"]),
            "geocoded_count": sum(1 for customer in customers if customer.get("lat") and customer.get("lng")),
        }

    def list_routes(self) -> list[RouteSummary]:
        tables = self._tables()
        stops_by_transport = self._stops_by_transport(tables)
        transport_count_by_route: dict[str, int] = {}
        stop_count_by_route: dict[str, int] = {}
        for transport in tables["transports"]:
            route_id = transport.get("route_id")
            if route_id is None:
                continue
            transport_count_by_route[route_id] = transport_count_by_route.get(route_id, 0) + 1
            stop_count_by_route[route_id] = stop_count_by_route.get(route_id, 0) + len(
                stops_by_transport.get(transport["id"], [])
            )
        return [
            RouteSummary(
                route_code=str(route.get("code") or route.get("name") or route["id"]),
                transport_count=transport_count_by_route.get(route["id"], 0),
                stop_count=stop_count_by_route.get(route["id"], 0),
            )
            for route in tables["routes"]
        ]

    def list_drivers_with_zones(
        self, top_n: int = 3
    ) -> list[DriverWithZones]:
        """Drivers + their top-N most-familiar zones derived from history.
        Drivers without any historical transports come back with empty
        top_zones / total_visits=0 — useful for the catalog UI."""
        db = db_service.load()
        familiarity = driver_zone_familiarity(db)
        out: list[DriverWithZones] = []
        for driver in db["tables"].get("drivers", []):
            zones = familiarity.get(driver["id"], {})
            top = sorted(zones.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
            out.append(
                DriverWithZones(
                    id=str(driver["id"]),
                    name=str(driver.get("name") or ""),
                    top_zones=[
                        DriverZoneStat(zone_code=z, visits=v) for z, v in top
                    ],
                    total_visits=sum(zones.values()),
                )
            )
        out.sort(key=lambda d: d.name)
        return out

    def list_transports(self) -> list[TransportSummary]:
        tables = self._tables()
        routes = self._by_id(tables["routes"])
        drivers = self._by_id(tables["drivers"])
        trucks = self._by_id(tables["trucks"])
        stops_by_transport = self._stops_by_transport(tables)
        summaries: list[TransportSummary] = []
        for transport in tables["transports"]:
            route = routes.get(transport.get("route_id"), {})
            driver = drivers.get(transport.get("driver_id"), {})
            truck = trucks.get(transport.get("truck_id"), {})
            summaries.append(
                TransportSummary(
                    transport_id=str(transport["id"]),
                    route_code=str(route.get("code") or route.get("name") or ""),
                    driver_name=str(driver.get("name") or ""),
                    date=self._date_or_today(transport.get("transport_date")),
                    stop_count=len(stops_by_transport.get(transport["id"], [])),
                    truck_type=self._truck_type(truck),
                )
            )
        return summaries

    def get_transport(self, transport_id: str) -> TransportDetail | None:
        tables = self._tables()
        transport = self._by_id(tables["transports"]).get(transport_id)
        if transport is None:
            return None

        routes = self._by_id(tables["routes"])
        drivers = self._by_id(tables["drivers"])
        trucks = self._by_id(tables["trucks"])
        route = routes.get(transport.get("route_id"), {})
        driver = drivers.get(transport.get("driver_id"), {})
        truck = trucks.get(transport.get("truck_id"), {})
        transport_date = self._date_or_today(transport.get("transport_date"))
        truck_type = self._truck_type(truck)
        stops = self._build_stops(tables, transport["id"], transport_date)

        # Persisted plan wins (it's the optimizer's exact packing). When
        # absent, derive a plan from the actual stop products so the truck
        # visualization shows the real cargo instead of falling back to a
        # client-side mock. See services/load_derivation.py.
        load_plan = self._load_plan(transport.get("load_plan_json"))
        if load_plan is None and stops:
            load_plan = derive_load_plan(
                transport_id=str(transport["id"]),
                truck_type=truck_type,
                transport_date=transport_date,
                stops=stops,
            )

        return TransportDetail(
            transport_id=str(transport["id"]),
            route_code=str(route.get("code") or route.get("name") or ""),
            driver_id=str(driver.get("id") or ""),
            driver_name=str(driver.get("name") or ""),
            date=transport_date,
            truck_type=truck_type,
            stops=stops,
            load_plan=load_plan,
        )

    def _load_plan(self, raw: Any) -> LoadPlan | None:
        """Parse the stashed LoadPlan dict back into the model. Defensive —
        rows persisted before the field existed return None."""
        if not isinstance(raw, dict):
            return None
        try:
            return LoadPlan.model_validate(raw)
        except Exception:
            return None

    def get_customer(self, customer_id: str) -> CustomerDetail | None:
        tables = self._tables()
        customer = self._by_id(tables["customers"]).get(customer_id)
        if customer is None:
            return None
        windows: dict[int, TimeWindow] = {}
        for row in tables["customer_time_windows"]:
            if row.get("customer_id") != customer_id:
                continue
            window = self._time_window(row)
            if window is not None:
                windows[int(row.get("weekday") or 0)] = window
        return CustomerDetail(
            customer_id=str(customer["id"]),
            name=str(customer.get("name") or ""),
            address=str(customer.get("address") or ""),
            city=str(customer.get("city") or ""),
            postal_code=str(customer.get("postal_code") or ""),
            lat=customer.get("lat"),
            lng=customer.get("lng"),
            time_windows=windows,
        )

    def _build_stops(
        self,
        tables: dict[str, list[dict[str, Any]]],
        transport_id: str,
        transport_date: date,
    ) -> list[DeliveryStop]:
        customers = self._by_id(tables["customers"])
        stops = [
            stop
            for stop in tables["delivery_stops"]
            if stop.get("transport_id") == transport_id
        ]
        stops.sort(key=lambda row: int(row.get("sequence") or 0))
        return [
            self._build_stop(tables, stop, customers.get(stop.get("customer_id"), {}), transport_date)
            for stop in stops
        ]

    def _build_stop(
        self,
        tables: dict[str, list[dict[str, Any]]],
        stop: dict[str, Any],
        customer: dict[str, Any],
        transport_date: date,
    ) -> DeliveryStop:
        return DeliveryStop(
            stop_id=str(stop["id"]),
            sequence=int(stop.get("sequence") or 0),
            customer_id=str(stop.get("customer_id") or ""),
            customer_name=str(customer.get("name") or ""),
            address=str(customer.get("address") or ""),
            postal_code=str(customer.get("postal_code") or ""),
            city=str(customer.get("city") or ""),
            lat=stop.get("lat") if stop.get("lat") is not None else customer.get("lat"),
            lng=stop.get("lng") if stop.get("lng") is not None else customer.get("lng"),
            time_window=self._window_for_customer(tables, customer.get("id"), transport_date),
            products=self._stop_products(tables, stop),
        )

    def _stop_products(
        self,
        tables: dict[str, list[dict[str, Any]]],
        stop: dict[str, Any],
    ) -> list[ProductLine]:
        """Per-stop products. Optimizer-persisted stops carry a products_json
        column on the row (set by route_persistence). For legacy/seeded
        stops we fall back to walking delivery_lines -> orders -> materials.
        Both paths return the same ProductLine shape."""
        raw = stop.get("products_json")
        if isinstance(raw, list):
            try:
                return [ProductLine.model_validate(item) for item in raw]
            except Exception:
                pass
        return self._products_for_stop(tables, stop["id"])

    def _products_for_stop(
        self,
        tables: dict[str, list[dict[str, Any]]],
        stop_id: str,
    ) -> list[ProductLine]:
        orders = self._by_id(tables["orders"])
        materials = self._by_id(tables["materials"])
        material_types = self._by_id(tables["material_types"])
        dimensions_by_material = self._dimensions_by_material(tables["material_dimensions"])
        products: list[ProductLine] = []
        for line in tables["delivery_lines"]:
            if line.get("delivery_stop_id") != stop_id:
                continue
            order = orders.get(line.get("order_id"))
            if order is None:
                continue
            material = materials.get(order.get("material_id"), {})
            material_type = material_types.get(material.get("material_type_id"), {})
            unit = self._product_unit(order.get("sales_unit") or material.get("base_unit"))
            products.append(
                ProductLine(
                    material_code=str(order.get("material_id") or ""),
                    description=str(material.get("description") or ""),
                    quantity=max(0, round(float(order.get("quantity") or 0))),
                    unit=unit,
                    category=self._product_category(material_type.get("name")),
                    is_returnable=bool(material.get("is_returnable")),
                    dimensions=self._dimensions_for_material(
                        dimensions_by_material.get(order.get("material_id"), []),
                        unit,
                    ),
                )
            )
        return products

    def _window_for_customer(
        self,
        tables: dict[str, list[dict[str, Any]]],
        customer_id: str | None,
        transport_date: date,
    ) -> TimeWindow | None:
        if customer_id is None:
            return None
        weekday = transport_date.isoweekday()
        fallback: TimeWindow | None = None
        for row in tables["customer_time_windows"]:
            if row.get("customer_id") != customer_id:
                continue
            window = self._time_window(row)
            if window is None:
                continue
            if int(row.get("weekday") or 0) == weekday:
                return window
            fallback = fallback or window
        return fallback

    def _time_window(self, row: dict[str, Any]) -> TimeWindow | None:
        open_time = self._parse_time(row.get("open_time"))
        close_time = self._parse_time(row.get("close_time"))
        if open_time is None or close_time is None:
            return None
        return TimeWindow(open=open_time, close=close_time)

    def _dimensions_for_material(
        self,
        rows: list[dict[str, Any]],
        unit: ProductUnit,
    ) -> ProductDimensions | None:
        if not rows:
            return None
        row = next((item for item in rows if item.get("unit") == unit.value), rows[0])
        return ProductDimensions(
            length_cm=float(row.get("length_cm") or 40),
            width_cm=float(row.get("width_cm") or 30),
            height_cm=float(row.get("height_cm") or 25),
            volume_l=row.get("volume_l"),
            weight_gross_kg=float(row.get("weight_gross_kg") or 15),
            weight_net_kg=row.get("weight_net_kg"),
        )

    def _dimensions_by_material(self, rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            material_id = row.get("material_id")
            if material_id is not None:
                grouped.setdefault(material_id, []).append(row)
        return grouped

    def _stops_by_transport(self, tables: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for stop in tables["delivery_stops"]:
            transport_id = stop.get("transport_id")
            if transport_id is not None:
                grouped.setdefault(transport_id, []).append(stop)
        return grouped

    def _by_id(self, rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        return {row["id"]: row for row in rows if row.get("id") is not None}

    def _date_or_today(self, value: Any) -> date:
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError:
                pass
        return date.today()

    def _parse_time(self, value: Any) -> time | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            return time.fromisoformat(value)
        except ValueError:
            return None

    def _product_unit(self, value: Any) -> ProductUnit:
        try:
            return ProductUnit(str(value or "").upper())
        except ValueError:
            return ProductUnit.UN

    def _product_category(self, name: Any) -> ProductCategory:
        key = str(name or "").lower().replace("&", "").replace(" ", "_")
        aliases = {
            "wine__spirits": ProductCategory.WINE_SPIRITS,
            "wine_spirits": ProductCategory.WINE_SPIRITS,
        }
        if key in aliases:
            return aliases[key]
        try:
            return ProductCategory(key)
        except ValueError:
            return ProductCategory.FOOD

    def _truck_type(self, truck: dict[str, Any]) -> TruckType:
        capacity = int(truck.get("capacity_pallets") or 6)
        if capacity >= 8:
            return TruckType.TRUCK_8
        return TruckType.TRUCK_6


repository = DbRepository()
