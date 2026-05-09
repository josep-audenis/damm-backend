from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from datetime import date as DateType
from datetime import datetime, time
from math import atan2, ceil, cos, radians, sin, sqrt
from uuid import uuid4

from models.domain import (
    DeliveryStop,
    LoadPlan,
    OptimizationResult,
    Pallet,
    PickInstruction,
    ProductCategory,
    ProductDimensions,
    ProductLine,
    ProductUnit,
    RouteResult,
    TruckType,
    TruckVisualization,
    VizPallet,
)
from models.schemas import OptimizeRequest, TransportDetail
from services.coordinates import enrich_stops_from_local_coordinates
from services.db_provider import db_service


DEPOT_LAT = 41.5409
DEPOT_LNG = 2.2134
PALLET_VOLUME_L = 120.0 * 80.0 * 170.0 / 1000.0
PALLET_WEIGHT_KG = 700.0
PALLET_SLOT_BY_TRUCK = {
    TruckType.TRUCK_6: 6,
    TruckType.TRUCK_8: 8,
    TruckType.VAN: 2,
}


@dataclass(frozen=True)
class Matrix:
    distance_km: list[list[float]]
    time_min: list[list[int]]


class OptimizationService:
    def optimize(self, transport: TransportDetail, request: OptimizeRequest) -> OptimizationResult:
        grouped_stops = group_stops_by_customer(enrich_stops_from_local_coordinates(transport.stops))
        matrix = build_distance_time_matrix(grouped_stops)
        route_indices, solver_name = solve_route(
            grouped_stops,
            matrix,
            request.truck_type,
            request.respect_time_windows,
            request.solver_time_limit_s,
        )
        ordered_stops = apply_route(grouped_stops, route_indices)
        route = build_route_result(transport, request, ordered_stops, route_indices, matrix, solver_name)
        load = build_load_plan(transport, request, ordered_stops)
        viz = build_truck_visualization(load, ordered_stops)
        now = datetime.now(UTC)
        return OptimizationResult(
            job_id=uuid4().hex[:8],
            transport_id=transport.transport_id,
            status="done",
            created_at=now,
            completed_at=now,
            route=route,
            routes=[route],
            load=load,
            loads=[load],
            viz=viz,
        )

    def optimize_orders(self, request: OptimizeRequest, job_id: str | None = None) -> OptimizationResult:
        plan = build_order_plan(request)
        matrix = build_distance_time_matrix(plan.stops)
        route_indices_by_vehicle, solver_name = solve_multi_vehicle_route(
            plan.stops,
            matrix,
            plan.truck_capacities,
            request.respect_time_windows,
            request.solver_time_limit_s,
        )
        routes: list[RouteResult] = []
        loads: list[LoadPlan] = []
        generated_transport_ids: list[str] = []
        for vehicle_index, route_indices in enumerate(route_indices_by_vehicle):
            if len(route_indices) <= 2:
                continue
            truck = plan.trucks[vehicle_index]
            ordered_stops = apply_route(plan.stops, route_indices)
            transport = TransportDetail(
                transport_id=f"planned-{job_id or uuid4().hex[:8]}-{vehicle_index + 1}",
                route_code=f"OPT-{vehicle_index + 1:02d}",
                driver_id="",
                driver_name=truck.get("plate") or f"Truck {vehicle_index + 1}",
                date=request.date or plan.date,
                truck_type=truck_type_from_capacity(plan.truck_capacities[vehicle_index]),
                stops=ordered_stops,
            )
            route = build_route_result(transport, request, ordered_stops, route_indices, matrix, solver_name)
            route.explanation = (
                f"{solver_name}; multi-vehicle CVRPTW; open orders grouped by customer; "
                "generated routes/transports from optimization"
            )
            load = build_load_plan(transport, request, ordered_stops)
            routes.append(route)
            loads.append(load)
            if request.persist_plan:
                generated_transport_ids.append(persist_generated_route(plan, truck, route, ordered_stops))

        now = datetime.now(UTC)
        status_id = ",".join(generated_transport_ids) if generated_transport_ids else "planned"
        return OptimizationResult(
            job_id=job_id or uuid4().hex[:8],
            transport_id=status_id,
            status="done",
            created_at=now,
            completed_at=now,
            route=routes[0] if routes else None,
            routes=routes,
            load=loads[0] if loads else None,
            loads=loads,
            viz=build_truck_visualization(loads[0], routes[0].ordered_stops) if routes and loads else None,
        )


@dataclass(frozen=True)
class OrderPlan:
    date: DateType
    warehouse: dict
    trucks: list[dict]
    truck_capacities: list[int]
    stops: list[DeliveryStop]
    order_ids_by_stop_id: dict[str, list[str]]


def build_order_plan(request: OptimizeRequest) -> OrderPlan:
    warehouses = db_service.list_rows("warehouses", limit=10000)
    warehouse = (
        next((row for row in warehouses if row.get("id") == request.warehouse_id), None)
        if request.warehouse_id
        else (warehouses[0] if warehouses else {})
    )
    trucks = db_service.list_rows("trucks", limit=10000)
    if request.truck_ids:
        truck_id_set = set(request.truck_ids)
        trucks = [truck for truck in trucks if truck.get("id") in truck_id_set]
    if not trucks:
        trucks = [{"id": None, "plate": "virtual-6pal", "capacity_pallets": PALLET_SLOT_BY_TRUCK[TruckType.TRUCK_6]}]

    customers = {row["id"]: row for row in db_service.list_rows("customers", limit=1000000)}
    materials = {row["id"]: row for row in db_service.list_rows("materials", limit=1000000)}
    dimensions = material_dimensions_by_material()
    windows = customer_windows_by_customer()
    orders = [
        row
        for row in db_service.list_rows("orders", limit=1000000)
        if not row.get("delivered_flag") and (request.date is None or row.get("due_date") == request.date.isoformat())
    ][: request.max_orders]
    if not orders:
        raise ValueError("No open orders match optimization request")

    by_customer: dict[str, list[dict]] = {}
    for order in orders:
        by_customer.setdefault(order["customer_id"], []).append(order)

    weekday = (request.date or DateType.today()).isoweekday()
    stops: list[DeliveryStop] = []
    order_ids_by_stop_id: dict[str, list[str]] = {}
    for sequence, (customer_id, customer_orders) in enumerate(by_customer.items(), start=1):
        customer = customers.get(customer_id)
        if customer is None:
            continue
        products = [product_line_from_order(order, materials, dimensions) for order in customer_orders]
        time_window = windows.get((customer_id, weekday))
        stop_id = f"plan-{customer_id}"
        order_ids_by_stop_id[stop_id] = [order["id"] for order in customer_orders]
        stops.append(
            DeliveryStop(
                stop_id=stop_id,
                sequence=sequence,
                customer_id=customer_id,
                customer_name=customer.get("name") or customer_id,
                address=customer.get("address") or "",
                postal_code=str(customer.get("postal_code") or ""),
                city=customer.get("city") or "",
                lat=customer.get("lat"),
                lng=customer.get("lng"),
                time_window=time_window,
                products=products,
                albaran_numbers=[order["id"] for order in customer_orders],
            )
        )

    if not stops:
        raise ValueError("Open orders do not reference known customers")
    capacities = [int(truck.get("capacity_pallets") or PALLET_SLOT_BY_TRUCK[TruckType.TRUCK_6]) for truck in trucks]
    return OrderPlan(
        date=request.date or DateType.today(),
        warehouse=warehouse,
        trucks=trucks,
        truck_capacities=capacities,
        stops=enrich_stops_from_local_coordinates(stops),
        order_ids_by_stop_id=order_ids_by_stop_id,
    )


def product_line_from_order(order: dict, materials: dict[str, dict], dimensions: dict[str, ProductDimensions]) -> ProductLine:
    material = materials.get(order.get("material_id"), {})
    try:
        unit = ProductUnit(str(order.get("sales_unit") or "UN"))
    except ValueError:
        unit = ProductUnit.UN
    return ProductLine(
        material_code=str(order.get("material_id")),
        description=material.get("description") or str(order.get("material_id")),
        quantity=int(float(order.get("quantity") or 0)),
        unit=unit,
        category=ProductCategory.FOOD,
        is_returnable=bool(material.get("is_returnable")),
        dimensions=dimensions.get(order.get("material_id")) or ProductDimensions(),
    )


def material_dimensions_by_material() -> dict[str, ProductDimensions]:
    output = {}
    for row in db_service.list_rows("material_dimensions", limit=1000000):
        material_id = row.get("material_id")
        if material_id in output:
            continue
        output[material_id] = ProductDimensions(
            length_cm=float(row.get("length_cm") or 40.0),
            width_cm=float(row.get("width_cm") or 30.0),
            height_cm=float(row.get("height_cm") or 25.0),
            volume_l=row.get("volume_l"),
            weight_gross_kg=float(row.get("weight_gross_kg") or 15.0),
            weight_net_kg=row.get("weight_net_kg"),
        )
    return output


def customer_windows_by_customer() -> dict[tuple[str, int], object]:
    from models.domain import TimeWindow

    output = {}
    for row in db_service.list_rows("customer_time_windows", limit=1000000):
        open_time = row.get("open_time")
        close_time = row.get("close_time")
        if not open_time or not close_time:
            continue
        output[(row["customer_id"], int(row.get("weekday") or 0))] = TimeWindow(
            open=time.fromisoformat(open_time),
            close=time.fromisoformat(close_time),
        )
    return output


def solve_multi_vehicle_route(
    stops: list[DeliveryStop],
    matrix: Matrix,
    truck_capacities: list[int],
    respect_time_windows: bool,
    time_limit_s: int,
) -> tuple[list[list[int]], str]:
    ortools_routes = solve_multi_with_ortools(stops, matrix, truck_capacities, respect_time_windows, time_limit_s)
    if ortools_routes is not None:
        return ortools_routes, "or-tools"
    return greedy_multi_vehicle_routes(stops, matrix, truck_capacities), "greedy-multi-vehicle-2opt"


def solve_multi_with_ortools(
    stops: list[DeliveryStop],
    matrix: Matrix,
    truck_capacities: list[int],
    respect_time_windows: bool,
    time_limit_s: int,
) -> list[list[int]] | None:
    try:
        from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    except ImportError:
        return None

    vehicle_count = len(truck_capacities)
    manager = pywrapcp.RoutingIndexManager(len(stops) + 1, vehicle_count, 0)
    routing = pywrapcp.RoutingModel(manager)

    def time_callback(from_idx: int, to_idx: int) -> int:
        return matrix.time_min[manager.IndexToNode(from_idx)][manager.IndexToNode(to_idx)]

    transit_idx = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

    if respect_time_windows:
        routing.AddDimension(transit_idx, 30, 12 * 60, True, "Time")
        time_dim = routing.GetDimensionOrDie("Time")
        for position, stop in enumerate(stops, start=1):
            if stop.time_window is None:
                continue
            time_dim.CumulVar(manager.NodeToIndex(position)).SetRange(
                minutes_since_midnight(stop.time_window.open),
                minutes_since_midnight(stop.time_window.close),
            )

    def demand_callback(index: int) -> int:
        node = manager.IndexToNode(index)
        return 0 if node == 0 else int(ceil(stop_pallet_demand(stops[node - 1]) * 100))

    demand_idx = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_idx,
        0,
        [capacity * 100 for capacity in truck_capacities],
        True,
        "Capacity",
    )

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search_params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_params.time_limit.seconds = time_limit_s
    solution = routing.SolveWithParameters(search_params)
    if solution is None:
        return None

    routes = []
    for vehicle_index in range(vehicle_count):
        route = []
        index = routing.Start(vehicle_index)
        while not routing.IsEnd(index):
            route.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))
        route.append(manager.IndexToNode(index))
        routes.append(route)
    return routes


def greedy_multi_vehicle_routes(stops: list[DeliveryStop], matrix: Matrix, truck_capacities: list[int]) -> list[list[int]]:
    unvisited = set(range(1, len(stops) + 1))
    routes = []
    for capacity in truck_capacities:
        route = [0]
        current = 0
        used = 0.0
        while unvisited:
            feasible = [
                node
                for node in unvisited
                if used + stop_pallet_demand(stops[node - 1]) <= capacity
            ]
            if not feasible:
                break
            next_node = min(feasible, key=lambda node: matrix.time_min[current][node])
            route.append(next_node)
            unvisited.remove(next_node)
            used += stop_pallet_demand(stops[next_node - 1])
            current = next_node
        route.append(0)
        routes.append(two_opt_improve(route, matrix.time_min))
    if unvisited:
        raise ValueError(f"{len(unvisited)} customer stops do not fit available truck capacity")
    return routes


def truck_type_from_capacity(capacity: int) -> TruckType:
    if capacity <= 2:
        return TruckType.VAN
    if capacity >= 8:
        return TruckType.TRUCK_8
    return TruckType.TRUCK_6


def persist_generated_route(plan: OrderPlan, truck: dict, route: RouteResult, ordered_stops: list[DeliveryStop]) -> str:
    transport = db_service.insert_row(
        "transports",
        {
            "transport_date": route.date.isoformat(),
            "route_id": None,
            "driver_id": None,
            "truck_id": truck.get("id"),
        },
    )
    for stop in ordered_stops:
        stop_row = db_service.insert_row(
            "delivery_stops",
            {
                "transport_id": transport["id"],
                "customer_id": stop.customer_id,
                "sequence": stop.sequence,
                "lat": stop.lat,
                "lng": stop.lng,
            },
        )
        for order_id in plan.order_ids_by_stop_id.get(stop.stop_id, []):
            db_service.insert_row(
                "delivery_lines",
                {
                    "delivery_stop_id": stop_row["id"],
                    "order_id": order_id,
                },
            )
    return str(transport["id"])


def group_stops_by_customer(stops: list[DeliveryStop]) -> list[DeliveryStop]:
    grouped: dict[str, DeliveryStop] = {}
    for stop in sorted(stops, key=lambda item: item.sequence):
        existing = grouped.get(stop.customer_id)
        if existing is None:
            grouped[stop.customer_id] = stop.model_copy(deep=True)
            continue
        existing.stop_id = f"{existing.stop_id}+{stop.stop_id}"
        existing.sequence = min(existing.sequence, stop.sequence)
        existing.products.extend(product.model_copy(deep=True) for product in stop.products)
        existing.returnables.extend(item.model_copy(deep=True) for item in stop.returnables)
        existing.albaran_numbers.extend(stop.albaran_numbers or [stop.stop_id])
        if existing.time_window is None:
            existing.time_window = stop.time_window
    return sorted(grouped.values(), key=lambda item: item.sequence)


def build_distance_time_matrix(stops: list[DeliveryStop], avg_speed_kmh: float = 30.0) -> Matrix:
    coords = [(DEPOT_LAT, DEPOT_LNG)] + [(stop.lat, stop.lng) for stop in stops]
    has_coords = all(lat is not None and lng is not None for lat, lng in coords)
    size = len(stops) + 1
    distances = [[0.0 for _ in range(size)] for _ in range(size)]
    times = [[0 for _ in range(size)] for _ in range(size)]
    for i in range(size):
        for j in range(size):
            if i == j:
                continue
            if has_coords:
                lat1, lng1 = coords[i]
                lat2, lng2 = coords[j]
                distance = haversine_km(float(lat1), float(lng1), float(lat2), float(lng2))
            else:
                distance = abs(i - j) * 2.0 if i and j else max(i, j) * 2.0
            distances[i][j] = round(distance, 3)
            times[i][j] = max(1, int(round((distance / avg_speed_kmh) * 60)))
    return Matrix(distance_km=distances, time_min=times)


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius_km = 6371.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * radius_km * atan2(sqrt(a), sqrt(1 - a))


def solve_route(
    stops: list[DeliveryStop],
    matrix: Matrix,
    truck_type: TruckType,
    respect_time_windows: bool,
    time_limit_s: int,
) -> tuple[list[int], str]:
    ortools_route = solve_with_ortools(stops, matrix, truck_type, respect_time_windows, time_limit_s)
    if ortools_route is not None:
        return ortools_route, "or-tools"
    route = nearest_neighbor_route(stops, matrix.time_min)
    return two_opt_improve(route, matrix.time_min), "nearest-neighbor-2opt"


def solve_with_ortools(
    stops: list[DeliveryStop],
    matrix: Matrix,
    truck_type: TruckType,
    respect_time_windows: bool,
    time_limit_s: int,
) -> list[int] | None:
    try:
        from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    except ImportError:
        return None

    manager = pywrapcp.RoutingIndexManager(len(stops) + 1, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def time_callback(from_idx: int, to_idx: int) -> int:
        return matrix.time_min[manager.IndexToNode(from_idx)][manager.IndexToNode(to_idx)]

    transit_idx = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

    if respect_time_windows:
        routing.AddDimension(transit_idx, 30, 12 * 60, True, "Time")
        time_dim = routing.GetDimensionOrDie("Time")
        for position, stop in enumerate(stops, start=1):
            if stop.time_window is None:
                continue
            start = minutes_since_midnight(stop.time_window.open)
            end = minutes_since_midnight(stop.time_window.close)
            time_dim.CumulVar(manager.NodeToIndex(position)).SetRange(start, end)

    def demand_callback(index: int) -> int:
        node = manager.IndexToNode(index)
        if node == 0:
            return 0
        return int(ceil(stop_pallet_demand(stops[node - 1]) * 100))

    demand_idx = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_idx,
        0,
        [PALLET_SLOT_BY_TRUCK.get(truck_type, 6) * 100],
        True,
        "Capacity",
    )

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search_params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_params.time_limit.seconds = time_limit_s

    solution = routing.SolveWithParameters(search_params)
    if solution is None:
        return None

    route = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        route.append(manager.IndexToNode(index))
        index = solution.Value(routing.NextVar(index))
    route.append(manager.IndexToNode(index))
    return route


def nearest_neighbor_route(stops: list[DeliveryStop], time_matrix: list[list[int]]) -> list[int]:
    unvisited = set(range(1, len(stops) + 1))
    route = [0]
    current = 0
    while unvisited:
        next_node = min(unvisited, key=lambda node: time_matrix[current][node])
        route.append(next_node)
        unvisited.remove(next_node)
        current = next_node
    route.append(0)
    return route


def two_opt_improve(route: list[int], time_matrix: list[list[int]]) -> list[int]:
    improved = True
    while improved:
        improved = False
        for i in range(1, len(route) - 2):
            for j in range(i + 1, len(route) - 1):
                delta = (
                    time_matrix[route[i - 1]][route[j]]
                    + time_matrix[route[i]][route[j + 1]]
                    - time_matrix[route[i - 1]][route[i]]
                    - time_matrix[route[j]][route[j + 1]]
                )
                if delta < 0:
                    route[i : j + 1] = reversed(route[i : j + 1])
                    improved = True
    return route


def apply_route(stops: list[DeliveryStop], route_indices: list[int]) -> list[DeliveryStop]:
    ordered = []
    for sequence, node in enumerate((node for node in route_indices if node != 0), start=1):
        stop = stops[node - 1].model_copy(deep=True)
        stop.sequence = sequence
        ordered.append(stop)
    return ordered


def build_route_result(
    transport: TransportDetail,
    request: OptimizeRequest,
    ordered_stops: list[DeliveryStop],
    route_indices: list[int],
    matrix: Matrix,
    solver_name: str,
    distance_source: str = "haversine",
) -> RouteResult:
    total_distance = sum(matrix.distance_km[a][b] for a, b in zip(route_indices, route_indices[1:]))
    total_time = sum(matrix.time_min[a][b] for a, b in zip(route_indices, route_indices[1:]))
    return RouteResult(
        transport_id=transport.transport_id,
        route_code=transport.route_code,
        driver_id=transport.driver_id,
        driver_name=transport.driver_name,
        truck_type=transport.truck_type,
        date=request.date or transport.date,
        ordered_stops=ordered_stops,
        total_distance_km=round(total_distance, 2),
        total_time_min=float(total_time),
        total_stops=len(ordered_stops),
        time_window_violations=find_time_window_violations(ordered_stops),
        has_tight_windows=any(stop.time_window is not None for stop in ordered_stops),
        explanation=f"{solver_name}; {distance_source}; orders grouped by customer; returns to DDI depot",
    )


def build_load_plan(transport: TransportDetail, request: OptimizeRequest, ordered_stops: list[DeliveryStop]) -> LoadPlan:
    pallet_slots_total = PALLET_SLOT_BY_TRUCK.get(request.truck_type, 6)
    pallets: list[Pallet] = []
    pick_list: list[PickInstruction] = []
    items_no_location: list[ProductLine] = []

    for stop in reversed(ordered_stops):
        remaining_weight = stop_weight_kg(stop)
        remaining_volume = stop_volume_l(stop)
        first_pallet_for_stop = True
        while remaining_weight > 0 or remaining_volume > 0:
            pallet = find_pallet_with_capacity(pallets, remaining_weight, remaining_volume)
            if pallet is None:
                pallet = Pallet(
                    pallet_index=len(pallets),
                    pallet_id=f"PAL-{len(pallets) + 1:03d}",
                )
                pallets.append(pallet)
            available_weight = max(0.0, PALLET_WEIGHT_KG - pallet.total_weight_kg)
            available_volume = max(0.0, PALLET_VOLUME_L - pallet.total_volume_l)
            placed_weight = min(remaining_weight, available_weight) if remaining_weight > 0 else 0.0
            placed_volume = min(remaining_volume, available_volume) if remaining_volume > 0 else 0.0
            if placed_weight <= 0 and placed_volume <= 0:
                break
            if stop.stop_id not in pallet.stop_ids:
                pallet.stop_ids.append(stop.stop_id)
            pallet.total_weight_kg = round(pallet.total_weight_kg + placed_weight, 2)
            pallet.total_volume_l = round(pallet.total_volume_l + placed_volume, 2)
            remaining_weight = round(max(0.0, remaining_weight - placed_weight), 2)
            remaining_volume = round(max(0.0, remaining_volume - placed_volume), 2)
            if first_pallet_for_stop:
                for product in stop.products:
                    if product.warehouse_location is None:
                        items_no_location.append(product)
                        continue
                    pick_list.append(
                        PickInstruction(
                            sequence=len(pick_list) + 1,
                            warehouse_location=product.warehouse_location,
                            material_code=product.material_code,
                            description=product.description,
                            quantity=product.quantity,
                            unit=product.unit,
                            pallet_id=pallet.pallet_id,
                            stop_id=stop.stop_id,
                        )
                    )
                first_pallet_for_stop = False

    pick_list.sort(key=lambda item: (item.warehouse_location, item.material_code))
    for sequence, item in enumerate(pick_list, start=1):
        item.sequence = sequence

    return_pallet = None
    if request.include_returnables:
        return_pallet = Pallet(
            pallet_index=len(pallets),
            pallet_id="PAL-RET",
            stop_ids=[stop.stop_id for stop in ordered_stops],
            is_returnables=True,
        )

    total_units = sum(product.quantity for stop in ordered_stops for product in stop.products)
    return LoadPlan(
        transport_id=transport.transport_id,
        truck_type=request.truck_type,
        date=request.date or transport.date,
        pallets=pallets,
        pick_list=pick_list,
        items_no_location=items_no_location,
        return_pallet=return_pallet,
        total_units_delivery=total_units,
        total_volume_delivery_l=round(sum(stop_volume_l(stop) for stop in ordered_stops), 2),
        total_weight_delivery_kg=round(sum(stop_weight_kg(stop) for stop in ordered_stops), 2),
        pallet_slots_used=len(pallets) + (1 if return_pallet else 0),
        pallet_slots_total=pallet_slots_total,
    )


def find_pallet_with_capacity(pallets: list[Pallet], weight_kg: float, volume_l: float) -> Pallet | None:
    for pallet in reversed(pallets):
        if pallet.is_returnables:
            continue
        has_weight = pallet.total_weight_kg < PALLET_WEIGHT_KG
        has_volume = pallet.total_volume_l < PALLET_VOLUME_L
        if has_weight and has_volume and (weight_kg > 0 or volume_l > 0):
            return pallet
    return None


def build_truck_visualization(
    load: LoadPlan,
    ordered_stops: list[DeliveryStop],
    route_geojson: dict | None = None,
) -> TruckVisualization:
    names = {stop.stop_id: stop.customer_name for stop in ordered_stops}
    colors = ["#2563eb", "#16a34a", "#f97316", "#dc2626", "#7c3aed", "#0891b2", "#4b5563"]
    viz_pallets = [
        VizPallet(
            pallet_id=pallet.pallet_id,
            label=names.get(pallet.stop_ids[0], pallet.pallet_id) if pallet.stop_ids else pallet.pallet_id,
            color=colors[index % len(colors)],
            position={"x": float(index % 2) * 90.0, "y": float(index // 2) * 130.0, "z": 0.0},
            dims={"l": 120.0, "w": 80.0, "h": max(30.0, min(170.0, pallet.total_volume_l / 9.6))},
            stop_ids=pallet.stop_ids,
            products_summary=[],
        )
        for index, pallet in enumerate(load.pallets)
    ]
    if load.return_pallet is not None:
        viz_pallets.append(
            VizPallet(
                pallet_id=load.return_pallet.pallet_id,
                label="Returnables",
                color="#64748b",
                position={"x": 180.0, "y": 0.0, "z": 0.0},
                dims={"l": 120.0, "w": 80.0, "h": 90.0},
                is_return=True,
                stop_ids=load.return_pallet.stop_ids,
                products_summary=["estimated returnables"],
            )
        )
    return TruckVisualization(pallets=viz_pallets, route_geojson=route_geojson)


def stop_pallet_demand(stop: DeliveryStop) -> float:
    volume_ratio = stop_volume_l(stop) / PALLET_VOLUME_L
    weight_ratio = stop_weight_kg(stop) / PALLET_WEIGHT_KG
    return max(volume_ratio, weight_ratio, 0.01)


def stop_volume_l(stop: DeliveryStop) -> float:
    return sum(product_volume_l(product) * product.quantity for product in stop.products)


def stop_weight_kg(stop: DeliveryStop) -> float:
    return sum(product_weight_kg(product) * product.quantity for product in stop.products)


def product_volume_l(product: ProductLine) -> float:
    dims = product.dimensions or ProductDimensions()
    if dims.volume_l is not None:
        return dims.volume_l
    return dims.length_cm * dims.width_cm * dims.height_cm / 1000.0


def product_weight_kg(product: ProductLine) -> float:
    dims = product.dimensions or ProductDimensions()
    return dims.weight_gross_kg


def minutes_since_midnight(value: time) -> int:
    return value.hour * 60 + value.minute


def find_time_window_violations(stops: list[DeliveryStop]) -> list[str]:
    violations = []
    for stop in stops:
        if stop.estimated_arrival is None or stop.time_window is None:
            continue
        if stop.estimated_arrival < stop.time_window.open or stop.estimated_arrival > stop.time_window.close:
            violations.append(stop.stop_id)
    return violations


optimization_service = OptimizationService()
