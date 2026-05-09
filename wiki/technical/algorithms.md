# Algorithms & Optimization Logic

## Problem Decomposition

The challenge is a combination of two classic NP-hard problems:

1. **CVRPTW** — Capacitated Vehicle Routing Problem with Time Windows (route optimization)
2. **3D Bin Packing** — packing items into a fixed-size container respecting physical constraints (load optimization)

Plus an additional logistics layer: **pickup & delivery** (returnables).

These two problems interact: the load order depends on the route, and the route affects how returnables are picked up and how capacity changes dynamically.

---

## 1. Route Optimization — CVRPTW

### Problem Formulation

- **Nodes**: depot (DDI Mollet warehouse) + N customer stops
- **Edges**: travel time between each pair of nodes (road time, not straight-line)
- **Constraints**:
  - Each stop must be visited within its time window `[open, close]`
  - Truck capacity (pallets or weight) must not be exceeded
  - Each stop visited exactly once
  - Route starts and ends at depot
- **Objective**: Minimize total travel time (or distance)

### OR-Tools Implementation

```python
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

def solve_vrp(stops: list[Stop], truck: Truck, time_matrix: list[list[int]]) -> list[int]:
    """
    Returns ordered list of stop indices (depot=0).
    time_matrix[i][j] = travel time in minutes from node i to node j.
    """
    n = len(stops) + 1  # +1 for depot
    manager = pywrapcp.RoutingIndexManager(n, 1, 0)  # 1 vehicle, depot=0
    routing = pywrapcp.RoutingModel(manager)

    # Time callback
    def time_callback(from_idx, to_idx):
        i = manager.IndexToNode(from_idx)
        j = manager.IndexToNode(to_idx)
        return time_matrix[i][j]
    
    transit_cb_idx = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_cb_idx)

    # Time window dimension
    routing.AddDimension(
        transit_cb_idx,
        slack_max=30,        # allow 30 min wait at a stop
        capacity=480,         # max 8h route
        fix_start_cumul_to_zero=True,
        name="Time"
    )
    time_dim = routing.GetDimensionOrDie("Time")

    for i, stop in enumerate(stops):
        node_idx = manager.NodeToIndex(i + 1)  # +1 because depot is 0
        if stop.time_window:
            open_min = stop.time_window.open.hour * 60 + stop.time_window.open.minute
            close_min = stop.time_window.close.hour * 60 + stop.time_window.close.minute
            time_dim.CumulVar(node_idx).SetRange(open_min, close_min)

    # Capacity dimension (in pallet units * 100 to use integers)
    def demand_callback(idx):
        node = manager.IndexToNode(idx)
        if node == 0:
            return 0
        return stops[node - 1].pallet_demand  # pre-computed fraction of pallet
    
    demand_cb_idx = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_cb_idx, 0, [truck.pallet_capacity * 100], True, "Capacity"
    )

    # Search parameters
    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_params.time_limit.seconds = 15  # hard limit for hackathon

    solution = routing.SolveWithParameters(search_params)
    
    if not solution:
        return fallback_nearest_neighbor(stops, time_matrix)
    
    return extract_route(routing, manager, solution)
```

### Fallback: Nearest Neighbor + 2-opt

If OR-Tools setup takes too long or solver fails, this always works:

```python
def nearest_neighbor_route(stops: list[Stop], time_matrix: list[list[int]]) -> list[int]:
    """Greedy nearest neighbor from depot (index 0)."""
    unvisited = set(range(1, len(stops) + 1))
    route = [0]
    current = 0
    
    while unvisited:
        # Find nearest unvisited stop that fits within time window
        best = min(unvisited, key=lambda j: time_matrix[current][j])
        route.append(best)
        unvisited.remove(best)
        current = best
    
    route.append(0)  # return to depot
    return route

def two_opt_improve(route: list[int], time_matrix) -> list[int]:
    """Classic 2-opt local search."""
    improved = True
    while improved:
        improved = False
        for i in range(1, len(route) - 2):
            for j in range(i + 1, len(route) - 1):
                delta = (
                    time_matrix[route[i-1]][route[j]] 
                    + time_matrix[route[i]][route[j+1]]
                    - time_matrix[route[i-1]][route[i]] 
                    - time_matrix[route[j]][route[j+1]]
                )
                if delta < 0:
                    route[i:j+1] = reversed(route[i:j+1])
                    improved = True
    return route
```

### Distance/Time Matrix Construction

**Option A — Haversine (fast, approximate, no API needed):**
```python
from math import radians, sin, cos, sqrt, atan2

def haversine_minutes(lat1, lng1, lat2, lng2, avg_speed_kmh=30) -> int:
    R = 6371
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng/2)**2
    dist_km = 2 * R * atan2(sqrt(a), sqrt(1-a))
    return int((dist_km / avg_speed_kmh) * 60)
```
Use `avg_speed_kmh=25` for urban Mollet, `35` for inter-city legs to Vic/Granollers.

**Option B — OpenRouteService API (real roads, free tier = 500 req/day):**
```python
import httpx

async def get_distance_matrix(coords: list[tuple]) -> list[list[float]]:
    url = "https://api.openrouteservice.org/v2/matrix/driving-hgv"
    headers = {"Authorization": ORS_API_KEY}
    body = {"locations": [[lng, lat] for lat, lng in coords], "metrics": ["duration"]}
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=body, headers=headers)
    return r.json()["durations"]  # seconds
```

> **Recommendation**: Use haversine first to get something working, swap to ORS later if time allows.

---

## 2. Load Optimization — Layer-Based 3D Bin Packing

### Simplified Model (recommended for 24h)

Instead of full 3D bin packing (which requires complex spatial indexing), use a **column stacking** model:

Each pallet is a 80×120cm base. Products are stacked in columns (a column = one product type stacked vertically). 

```
Pallet view (front):
┌─────────────────────────┐  ← 120cm wide
│  [barrel]  [barrel]     │
│  [ED13]×6  [VD13]×4     │  
│  [crate]×2 [crate]×2    │
└─────────────────────────┘  ← 80cm deep
Height: 170cm max
```

**Algorithm:**

```python
STACKING_RULES = {
    "barrel": {"max_height": 1, "stackable_on": []},          # never stack on barrels
    "crate_returnable": {"max_height": 4, "stackable_on": ["crate_returnable"]},
    "case_bottle": {"max_height": 6, "stackable_on": ["case_bottle", "case_can"]},
    "case_can": {"max_height": 8, "stackable_on": ["case_bottle", "case_can", "case_can"]},
    "small_box": {"max_height": 5, "stackable_on": ["case_bottle", "case_can", "small_box"]},
}

def classify_product(material_code: str, description: str) -> str:
    if "BRL" in material_code or "barrel" in description.lower():
        return "barrel"
    if material_code.startswith("CJ"):  # CJ13 = crate
        return "crate_returnable"
    if "LATA" in description or "SLEEK" in description:
        return "case_can"
    if material_code.startswith("0AG") or material_code.startswith("0LT"):
        return "case_bottle"  # water, soft drinks
    return "case_bottle"  # default

def pack_products_to_pallets(
    stops_in_order: list[Stop],
    truck: Truck,
    pallet_max_height_cm: float = 170.0
) -> list[Pallet]:
    pallets = []
    # Assign products to pallets: last stop first (deepest in truck)
    for stop in reversed(stops_in_order):
        pallet = Pallet(stop_id=stop.stop_id)
        current_height = 0
        
        # Sort products: heaviest (barrels) first, lightest last
        sorted_products = sorted(
            stop.products, 
            key=lambda p: p.weight_kg, 
            reverse=True
        )
        
        for product in sorted_products:
            product_type = classify_product(product.material_code, product.description)
            # Use case height from ZM040 dimensions
            layer_height = product.dimensions_cm[2]  # height of one case
            stacks = product.quantity  # could be multiple columns
            
            if current_height + layer_height <= pallet_max_height_cm:
                pallet.add_product(product)
                current_height += layer_height
            else:
                # Overflow: create second pallet for this stop
                pallets.append(pallet)
                pallet = Pallet(stop_id=stop.stop_id + "_2")
                pallet.add_product(product)
                current_height = layer_height
        
        pallets.append(pallet)
    
    # Reserve rear pallet position for returnables
    returnables_pallet = Pallet(stop_id="RETURNABLES", is_returnables=True)
    pallets.append(returnables_pallet)
    
    return pallets  # order: first stop's pallet at front (index 0)
```

### Returnable Logistics Model

~60% of products are returnable (bottles, crates). The model needs to:

1. **Predict pickups**: From historical data, for each customer + material, calculate the expected returnables ratio. If delivering 10 ED13 (Estrella Damm 1/3), typically expect to pick up 8–10 CJ13 (empty crates).

```python
def estimate_returnables(stop: Stop) -> list[ProductLine]:
    """Estimate returnables pickup based on historical delivery patterns."""
    returnables = []
    for product in stop.products:
        if is_returnable_material(product.material_code):
            # Assume 90% return rate for bottles, 100% for crates
            return_qty = int(product.quantity * 0.9)
            returnables.append(ProductLine(
                material_code=get_returnable_code(product.material_code),
                quantity=return_qty,
                is_pickup=True,
                ...
            ))
    return returnables
```

2. **Capacity accounting**: As the route progresses, capacity decreases (delivering) but also increases (picking up returnables). This creates a dynamic capacity problem. For the hackathon, model it simply:

```
effective_capacity(stop_i) = base_capacity 
    - sum(deliveries before stop_i) 
    + sum(returnables picked up before stop_i)
```

3. **Returnables pallet**: Keep a dedicated pallet slot (or partial slot) at the rear of the truck specifically for accumulating returnables during the route.

---

## 3. Warehouse Pick Path Optimization

After computing the load plan, generate an optimal picking order for the warehouse workers:

- Each product has a warehouse location code (e.g., `FA05A2` = Aisle F, Bay A, Position 05, Level A2).
- Group products by aisle/bay to minimize travel within the warehouse.
- Output an ordered picking list: "Go to FA05A2 → pick 6× ED13. Go to CB06A2 → pick 24× Schweppes Tónica. Go to DB06A1 → pick 12× Bitter KAS."

```python
def generate_pick_list(load_plan: list[Pallet]) -> list[PickItem]:
    """Generate warehouse pick sequence, grouped by location."""
    all_items = []
    for pallet in load_plan:
        for product in pallet.products:
            all_items.append(PickItem(
                location=product.warehouse_location,
                material=product.material_code,
                description=product.description,
                quantity=product.quantity,
                pallet_id=pallet.pallet_id,
            ))
    
    # Sort by warehouse location (aisle-major, bay-minor)
    # Location format: XX##Y# — first char = aisle, then bay, etc.
    all_items.sort(key=lambda x: x.location)
    
    return all_items
```

Location sort key: `FA05A2` → sort by `F` first (aisle), then `A` (sub-aisle), then `05` (bay number), then `A2` (shelf level).

---

## 4. Model Evaluation (how to validate results)

Since this is a hackathon with real data, validate against historical routes:

```python
def evaluate_against_historical(
    optimized_route: RouteResult,
    historical_transport_id: str
) -> EvalMetrics:
    historical = load_historical_transport(historical_transport_id)
    
    return EvalMetrics(
        distance_improvement_pct=...,   # optimized vs historical total distance
        time_window_violations_before=historical.violations,
        time_window_violations_after=len(optimized_route.time_window_violations),
        estimated_time_saved_min=...,
    )
```

**Expected results to show judges**: 5–15% distance reduction, 0 time window violations vs some in historical data.

---

## 5. Complexity & Performance Notes

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| Haversine matrix (N stops) | O(N²) | N≤25 → instant |
| OR-Tools CVRPTW | NP-hard | 15s limit, good heuristics → practical solutions |
| Nearest neighbor | O(N²) | Always fast, ≤ 1ms for N=25 |
| 2-opt | O(N²) per pass | Usually converges in 5–10 passes |
| Layer-based bin packing | O(N×M) | N stops, M products per stop |
| Warehouse pick sort | O(P log P) | P = total product lines |

All operations are well within real-time response requirements for a single route (N≤25 stops). API response time should be < 5 seconds total.
