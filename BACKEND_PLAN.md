# Backend Architecture Plan — Damm Smart Truck

## Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Framework | **FastAPI** | Async, fast to scaffold, automatic OpenAPI docs |
| Optimization | **OR-Tools** (Google) | Best-in-class VRP + bin-packing, Python bindings, free |
| Geo/Routing | **OSRM** (self-hosted) or **OpenRouteService API** | Free tier, real road distances & times |
| Geocoding | **Nominatim** (OSM) or **Google Maps Geocoding API** | Convert addresses to lat/lng |
| Data loading | **pandas** + **openpyxl** | Already have Excel data, fast parsing |
| Caching | **functools.lru_cache** / in-memory dict | No time to set up Redis; cache geocoded addresses and parsed data |
| Gemini (optional) | **google-generativeai** SDK | Agent layer for natural language explanations |
| Serialization | **Pydantic v2** | Built into FastAPI, great for validation |
| CORS | FastAPI `CORSMiddleware` | Frontend on different port |

---

## API Design

### Base URL: `http://localhost:8000/api/v1`

### Core Endpoints

#### Data / Setup
```
GET  /data/routes          → list all available routes (DR codes) with driver names
GET  /data/customers       → list customers with addresses and time windows
GET  /data/materials       → list products with dimensions and warehouse locations
GET  /data/transports      → list transports (optionally filter by date or route)
GET  /data/transport/{id}  → full detail of one transport's stops and products
POST /data/ingest          → (re)load and reparse the Excel files into memory
```

#### Route Optimization
```
POST /optimize/route
  Body: {
    transport_id: str,          # existing transport to optimize, OR
    stops: [StopInput],         # custom list of stops
    truck_type: "6pal"|"8pal"|"van",
    date: "YYYY-MM-DD",
    respect_time_windows: bool  # default true
  }
  Response: {
    ordered_stops: [Stop],
    total_distance_km: float,
    total_time_min: float,
    time_window_violations: [...],
    explanation: str
  }
```

#### Load Optimization
```
POST /optimize/load
  Body: {
    ordered_stops: [Stop],      # output from route optimizer, or manual order
    truck_type: "6pal"|"8pal"|"van",
    include_returnables: bool   # default true
  }
  Response: {
    pallets: [Pallet],          # ordered list from front to back
    load_sequence: [LoadInstruction],   # ordered picking list for warehouse
    visualization_data: TruckViz,
    warehouse_pick_path: [PickItem],
    alerts: [str]
  }
```

#### Combined (main endpoint for MVP)
```
POST /optimize/full
  Body: {
    transport_id: str,
    truck_type: "6pal"|"8pal"|"van"
  }
  Response: {
    route: RouteResult,
    load: LoadResult,
    summary: str
  }
```

#### Agent (optional, Gemini-powered)
```
POST /agent/explain
  Body: { result_id: str, question: str }
  Response: { answer: str, citations: [...] }

POST /agent/suggest
  Body: { transport_id: str, context: str }
  Response: { suggestions: [Suggestion] }
```

---

## Data Pipeline

```
Excel files (raw)
    ↓ data_loader.py (pandas)
Normalized in-memory DataFrames
    ↓ geocoding.py
Customers enriched with lat/lng
    ↓ domain.py models
Stop, Product, Truck objects (Pydantic)
    ↓ vrp_solver.py / bin_packing.py
OptimizedRoute, LoadPlan
    ↓ FastAPI response serialization
JSON → Frontend
```

### Data Loading Strategy

Since the data is static Excel files (provided by Damm), load everything at **startup** into memory using a global `AppState` singleton. No database needed for the hackathon.

```python
# services/data_loader.py
import pandas as pd
from functools import lru_cache

@lru_cache(maxsize=1)
def load_all_data() -> AppData:
    deliveries = pd.read_excel("data/raw/Hackaton.xlsx", sheet_name="Detalle entrega")
    headers = pd.read_excel("data/raw/Hackaton.xlsx", sheet_name="Cabecera Transporte")
    addresses = pd.read_excel("data/raw/Hackaton.xlsx", sheet_name="Direcciones")
    zones = pd.read_excel("data/raw/Hackaton.xlsx", sheet_name="ZONAS")
    materials_loc = pd.read_excel("data/raw/Hackaton.xlsx", sheet_name="Materiales zubic")
    time_windows = pd.read_excel("data/raw/Horarios Entrega.XLSX")
    dimensions = pd.read_excel("data/raw/ZM040.XLSX")
    layout = pd.read_excel("data/raw/Layout Mollet.xlsx", sheet_name="DDI MOLLET")
    return AppData(...)
```

---

## Domain Models (Pydantic)

```python
# models/domain.py

class TimeWindow(BaseModel):
    open: time
    close: time

class Stop(BaseModel):
    stop_id: str
    customer_id: str
    customer_name: str
    address: str
    lat: float
    lng: float
    time_window: TimeWindow | None
    products: list[ProductLine]
    returnables_pickup: list[ProductLine]  # what to pick up (logística inversa)
    priority: int  # from N.º Prioridad VIAJE

class ProductLine(BaseModel):
    material_code: str
    description: str
    quantity: int
    unit: str
    is_returnable: bool
    dimensions_cm: tuple[float, float, float]  # L x W x H
    weight_kg: float
    warehouse_location: str  # e.g. "FA05A2"

class Truck(BaseModel):
    truck_type: Literal["6pal", "8pal", "van"]
    pallet_capacity: int          # 6, 8, or 3
    pallet_dims_cm: tuple = (80, 120, 170)  # standard EUR pallet
    max_weight_kg: float = 10000.0

class Pallet(BaseModel):
    pallet_id: int
    stop_assignments: list[str]   # customer_ids this pallet serves
    products: list[ProductLine]
    total_volume_l: float
    total_weight_kg: float
    stack_height_cm: float
    access_side: Literal["lateral", "rear"]

class RouteResult(BaseModel):
    ordered_stops: list[Stop]
    total_distance_km: float
    total_time_min: float
    time_window_violations: list[str]
    explanation: str

class LoadResult(BaseModel):
    pallets: list[Pallet]          # front-to-back order
    load_sequence: list[str]       # ordered list of warehouse locations to pick
    visualization_data: dict       # for 3D viz in frontend
    alerts: list[str]
```

---

## Route Optimization Strategy

### Primary: OR-Tools CVRPTW (Capacitated VRP with Time Windows)

OR-Tools `routing` module handles this natively. Steps:

1. Build **distance matrix** between all stops (use real road distances from OSRM or approximate with haversine for speed).
2. Add **time window constraints** from `Horarios Entrega.XLSX`.
3. Add **capacity constraint** (pallet count — after bin-packing, each stop's products occupy some pallet fraction).
4. Add **returnable pickup demand** (negative demand in OR-Tools = pickup).
5. Run solver with time limit (e.g. 10–30 seconds depending on stop count).

### Fallback: Nearest Neighbor + 2-opt heuristic

If OR-Tools is too slow or hard to set up under time pressure, implement:
1. Start at depot (DDI Mollet warehouse).
2. Nearest neighbor greedy route construction, respecting time windows.
3. 2-opt local search to swap pairs of edges and improve total distance.

This runs in milliseconds and is easy to code in < 1 hour.

### Geocoding

Addresses are in the data (`Calle`, `CP`, `Población`). Geocode them once at startup:
- Use `geopy` with Nominatim or OpenRouteService.
- Cache results in a JSON file so re-runs don't re-geocode.
- Many stops are in Mollet del Vallès, Granollers, Vic — relatively small area, geocoding is fast.

---

## Load Optimization Strategy

### Primary: Layer-based Bin Packing (custom)

The truck has N pallets (6 or 8). Each pallet is loaded with products for one or more stops. Strategy:

1. **Assign products to pallets** — ideally one pallet per stop (for easy access), but group small stops onto shared pallets.
2. **Order pallets** — last delivery stop's pallet goes in first (deepest), first stop's pallet closest to the side door.
3. **Within each pallet** — heavy/large items at the bottom, light/fragile on top. Barrels at bottom, bottles in the middle, cans on top.
4. **Returnable space reservation** — reserve a partial pallet slot or the rear pallet for returnables being picked up during the route. As the route progresses, the truck fills back up with returnables.

### Layer-based Packing (simplified for hackathon)

Since real 3D bin-packing is NP-hard and complex to implement well in 24h, use a **layer stacking** model:
- Products are stacked vertically on a pallet in layers.
- Each layer = a row of boxes, laid flat.
- Track height per pallet (max 170cm for standard EUR pallet in the truck).
- Use product dimensions from `ZM040.XLSX` (CAJ = case unit, which is what's physically loaded).

```python
def pack_pallet(products: list[ProductLine], max_height_cm=170) -> Pallet:
    # Sort: heaviest/tallest first (barrels, then cases, then small items)
    # Stack until height limit reached
    # Return pallet with stacking instructions
```

### Hybrid Loading Model

The challenge brief explicitly asks to explore hybrid loading (by reference vs by client). The recommended approach:
- **High-volume products** (ED13 Estrella Damm 1/3 — appears in almost every stop): load a shared "reference pallet" accessible throughout.
- **Stop-specific products** (specialty items, small quantities): load client-specific mini-pallets.
- This is the creativity angle — demonstrate it as a configurable option.

---

## Gemini Agent Integration (Optional)

Use Google Gemini 1.5 Flash (fast, cheap) as a reasoning layer on top of the optimizer outputs.

### Two main uses:

**1. Explainability agent** — after optimization, the agent explains in natural language why a route or load config was chosen:
```
"The route visits Bar Granada before Raco del Semi Cachopo because Bar Granada 
has a tight delivery window of 08:00–09:00, while Raco is flexible. Loading 
pallet 2 first ensures Bar Granada's Estrella Damm barrels are accessible 
from the side door without moving other freight."
```

**2. Recommendation agent** — given a transport, suggests operational improvements beyond pure optimization:
```
"Customers in DD13100001 and DD13100002 are 200m apart but currently on 
different routes. Merging them would save 12 minutes per day."
```

### Implementation

```python
# services/gemini_agent.py
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

def explain_route(route: RouteResult, stops: list[Stop]) -> str:
    prompt = build_explanation_prompt(route, stops)
    response = model.generate_content(prompt)
    return response.text

def build_explanation_prompt(route: RouteResult, stops: list[Stop]) -> str:
    stop_summary = "\n".join([
        f"- Stop {i+1}: {s.customer_name} | window: {s.time_window} | "
        f"{sum(p.quantity for p in s.products)} units"
        for i, s in enumerate(route.ordered_stops)
    ])
    return f"""
You are a logistics expert. Explain in 3-5 sentences why this delivery route 
was optimized in this specific order. Be concrete and reference the actual 
customers and constraints.

Route stops (in order):
{stop_summary}

Total distance: {route.total_distance_km:.1f} km
Total time: {route.total_time_min:.0f} min
Violations: {route.time_window_violations or "None"}

Explain the key decisions made.
"""
```

---

## File-by-File Implementation Priority

### Phase 1 — Data Layer (first 3h)
- `services/data_loader.py` — parse all Excel files, build in-memory store
- `models/domain.py` — define all Pydantic models
- `services/geocoding.py` — geocode customer addresses, cache to JSON
- `routers/data.py` — `/data/routes`, `/data/transport/{id}` endpoints

### Phase 2 — Route Optimization (next 4h)
- `services/vrp_solver.py` — OR-Tools CVRPTW or nearest-neighbor fallback
- `routers/routes.py` — `/optimize/route` endpoint
- Test against 1–2 real transports from the data

### Phase 3 — Load Optimization (next 4h)
- `services/bin_packing.py` — layer-based pallet packing
- `routers/loading.py` — `/optimize/load` endpoint
- Wire `/optimize/full` combined endpoint

### Phase 4 — Polish & Agent (final hours)
- `services/gemini_agent.py` — explanation generation
- `routers/agents.py` — `/agent/explain` endpoint
- Error handling, CORS, cleanup

---

## Key Libraries

```txt
# requirements.txt
fastapi>=0.111.0
uvicorn[standard]>=0.29.0
pydantic>=2.7.0
pandas>=2.2.0
openpyxl>=3.1.2
ortools>=9.10.0
geopy>=2.4.1
httpx>=0.27.0
python-dotenv>=1.0.0
google-generativeai>=0.7.0   # optional, for Gemini
```

---

## Environment Variables

```env
# .env.example
GEMINI_API_KEY=your_key_here
ORS_API_KEY=your_openrouteservice_key  # optional, for real road distances
GEOCODING_CACHE_FILE=data/processed/geocache.json
DATA_DIR=data/raw
```

---

## Frontend Contract (for coordination)

The frontend team needs these response shapes. Agree on them early:

- **`/optimize/full`** is the primary endpoint — frontend passes `transport_id` and gets back everything.
- **`visualization_data`** in LoadResult should be a structured dict the frontend can render as a 3D truck view. Suggested format:
```json
{
  "truck_dims": {"length_cm": 620, "width_cm": 240, "height_cm": 240},
  "pallets": [
    {
      "pallet_id": 1,
      "position": {"x": 0, "y": 0, "z": 0},
      "dims": {"l": 120, "w": 80, "h": 140},
      "color": "#3b82f6",
      "label": "Stop 1 – Bar Granada",
      "products": [...]
    }
  ]
}
```
- Coordinate system: x = truck length (0 = front), y = width, z = height.
