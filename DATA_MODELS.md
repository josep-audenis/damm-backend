# Data Models & WebSocket Protocol

Ground truth for all Pydantic schemas and the real-time communication contract
between backend and frontend. Models are derived directly from DDI operational
documents: **Hoja Carga** (warehouse pick sheet), **Hoja Ruta** (driver route
sheet), and **Albarán** (delivery invoice).

---

## 1. Core Domain Models (`models/domain.py`)

### 1.1 Primitives

```python
from __future__ import annotations
from datetime import date, time, datetime
from decimal import Decimal
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field


class TruckType(str, Enum):
    TRUCK_6 = "6pal"    # 11 units in fleet
    TRUCK_8 = "8pal"    # 4 units in fleet
    VAN     = "van"     # 1 unit, 3 pallets


class PaymentCondition(str, Enum):
    CONTADO  = "CONTADO"   # Cash on delivery — driver collects
    CREDITO  = "CREDITO"   # Credit — no collection needed


class ProductUnit(str, Enum):
    CAJ  = "CAJ"   # Caja — case/box (most common)
    PAL  = "PAL"   # Pallet
    UN   = "UN"    # Unit
    BOT  = "BOT"   # Botella — bottle
    BRL  = "BRL"   # Barril — barrel/keg
    TUB  = "TUB"   # Tubo — gas tube (CO₂)
    PAK  = "PAK"   # Pack


class ProductCategory(str, Enum):
    BEER_BOTTLE    = "beer_bottle"    # ED13, VO13, FD13, DL13 — returnable bottles
    BEER_BARREL    = "beer_barrel"    # ED30, TU20, DL20, ID20 — kegs
    WATER          = "water"          # VE*, 0AG* — water/mineral
    SOFT_DRINK     = "soft_drink"     # 0RF* — cans, PET
    DAIRY          = "dairy"          # 0LT* — milk, lactose-free
    COFFEE         = "coffee"         # 0CF* — coffee, capsules
    WINE_SPIRITS   = "wine_spirits"   # 0VE*, 0LI* — wine, spirits
    FOOD           = "food"           # 0AM* — food items
    DISPOSABLE     = "disposable"     # 0LM* — napkins, bags, cleaning
    MERCHANDISE    = "merchandise"    # UE*, UC* — branded glasses, openers
    GAS            = "gas"            # TB8 — CO₂ gas bottles
    RETURNABLE_EMPTY = "returnable_empty"  # CJ13, BRL*V, 3ENV* — empty returns


class TimeWindow(BaseModel):
    open:  time
    close: time

    @property
    def duration_minutes(self) -> int:
        o = self.open.hour * 60 + self.open.minute
    c = self.close.hour * 60 + self.close.minute
        return c - o

    def is_tight(self) -> bool:
        """Flags windows ≤ 30 min — needs priority scheduling."""
        return self.duration_minutes <= 30
```

---

### 1.2 Product Models

```python
class ProductDimensions(BaseModel):
    """From ZM040.XLSX — case-level dimensions."""
    length_cm: float = 40.0
    width_cm:  float = 30.0
    height_cm: float = 25.0
    volume_l:  float | None = None
    weight_gross_kg: float = 15.0
    weight_net_kg:   float | None = None


class ProductLine(BaseModel):
    """
    One line on a Hoja Carga / Albarán.
    E.g.: AA09A1 | ED13 | ESTRELLA DAMM 1/3 RET. PP | 114 | Caja
    """
    material_code:      str           # e.g. "ED13", "0RF0088"
    description:        str           # e.g. "ESTRELLA DAMM 1/3 RET. PP"
    quantity:           int
    unit:               ProductUnit
    category:           ProductCategory
    is_returnable:      bool          # True for RET / bottles / kegs
    warehouse_location: str | None    # e.g. "AA09A1", "ZCG" — from Materiales zubic
    dimensions:         ProductDimensions | None = None

    # Albarán pricing fields (optional — for invoice display)
    unit_price:     Decimal | None = None
    discount_pct:   Decimal | None = None
    net_amount:     Decimal | None = None
    vat_rate:       Decimal | None = None  # 4, 10, or 21


class ReturnableItem(BaseModel):
    """
    Empty containers to PICK UP from customer.
    From Hoja Carga section 'Carga envases'.
    E.g.: CJ13 | CAJA DAMM+BOT. 1/3 RET VACIO | 161 | Caja
    """
    material_code: str    # e.g. "CJ13", "BRL30V", "3ENV0041"
    description:   str
    quantity:      int
    unit:          ProductUnit
    # Physical volume needed in truck for the return trip
    volume_l:      float | None = None
    weight_kg:     float | None = None
```

---

### 1.3 Stop / Delivery Models

```python
class DeliveryStop(BaseModel):
    """
    One customer stop in a route.
    Maps to one Entrega in Cabecera Transporte + its lines in Detalle entrega.
    Also maps to one row in Hoja Ruta.
    """
    # Identifiers
    stop_id:        str          # Entrega number, e.g. "828482379"
    sequence:       int          # Position in optimized route (1 = first)
    customer_id:    str          # Destinatario mcía., e.g. "9100627695"
    customer_name:  str          # e.g. "BAR PAVELLOS T JULIA VILATORTA"

    # Location
    address:        str          # Full street address
    postal_code:    str          # e.g. "08500"
    city:           str          # e.g. "Sant Julià de Vilatorta"
    lat:            float | None = None
    lng:            float | None = None

    # Scheduling
    time_window:    TimeWindow | None = None
    shift:          Literal[1, 2] = 1   # 1=morning, 2=afternoon
    estimated_arrival: time | None = None  # filled by optimizer

    # Products to deliver
    products:       list[ProductLine] = []

    # Returnables to pick up (logística inversa)
    returnables:    list[ReturnableItem] = []

    # Payment — from Hoja Ruta
    payment_condition: PaymentCondition = PaymentCondition.CREDITO
    invoice_total:  Decimal | None = None   # proforma total
    cash_to_collect: Decimal = Decimal("0") # only if CONTADO

    # Document numbers — from Albarán
    albaran_numbers: list[str] = []   # e.g. ["828482327", "841094453"]

    # Computed metrics (filled after optimization)
    travel_time_from_prev_min: float | None = None
    distance_from_prev_km:     float | None = None
```

---

### 1.4 Pallet & Load Models

```python
class PalletItem(BaseModel):
    """A product stacked on a specific pallet, with position info."""
    product:        ProductLine
    layer:          int     # 0 = floor layer, 1 = second layer, etc.
    column:         int     # left-to-right column index on pallet
    stack_height_cm: float  # cumulative height at this item's top


class Pallet(BaseModel):
    """
    One physical pallet in the truck.
    Pallets are ordered front-to-back: pallet_index=0 is nearest the side door.
    Last stop → first pallet (loaded last, accessed first).
    """
    pallet_index:       int      # 0 = front (first accessible), N-1 = rear
    pallet_id:          str      # e.g. "PAL-001"
    stop_ids:           list[str]  # which DeliveryStop(s) this pallet serves
    is_returnables:     bool = False  # True for the pickup/return pallet

    items:              list[PalletItem] = []
    total_height_cm:    float = 0.0
    total_weight_kg:    float = 0.0
    total_volume_l:     float = 0.0

    # For frontend 3D visualization
    position_in_truck: dict = Field(default_factory=dict)
    # e.g. {"x_cm": 0, "y_cm": 0, "z_cm": 0}  — x=truck length from front


class PickInstruction(BaseModel):
    """
    One line in the warehouse pick list (from Hoja Carga, sorted by Ubicación).
    Worker walks the warehouse in this order to build the load.
    """
    sequence:           int         # pick order (1 = first to pick)
    warehouse_location: str         # e.g. "AA09A1", "ZCG"
    material_code:      str
    description:        str
    quantity:           int
    unit:               ProductUnit
    pallet_id:          str         # which pallet this goes onto
    stop_id:            str         # which customer this is for


class LoadPlan(BaseModel):
    """
    Full truck loading plan — output of bin_packing.py.
    Mirrors the real Hoja Carga structure.
    """
    transport_id:       str
    truck_type:         TruckType
    vehicle_id:         str | None = None   # e.g. "V235045"
    date:               date

    pallets:            list[Pallet]        # ordered front→rear
    pick_list:          list[PickInstruction]  # warehouse walk order
    items_no_location:  list[ProductLine] = []  # ZCG or unknown location
    return_pallet:      Pallet | None = None    # returnables to pick up

    # Totals (mirrors Hoja Carga footer)
    total_units_delivery:   int   = 0
    total_units_return:     int   = 0
    total_volume_delivery_l: float = 0.0
    total_volume_return_l:  float = 0.0
    total_weight_delivery_kg: float = 0.0
    total_weight_return_kg: float = 0.0

    # Truck utilization
    pallet_slots_used:  int   = 0
    pallet_slots_total: int   = 0

    @property
    def utilization_pct(self) -> float:
        if self.pallet_slots_total == 0:
            return 0.0
        return round(self.pallet_slots_used / self.pallet_slots_total * 100, 1)
```

---

### 1.5 Route Models

```python
class RouteResult(BaseModel):
    """
    Optimized route — output of vrp_solver.py.
    Mirrors the real Hoja Ruta structure.
    """
    transport_id:   str
    route_code:     str             # e.g. "DR0027"
    driver_id:      str             # e.g. "850004"
    driver_name:    str             # e.g. "FRAN ROMERO"
    truck_type:     TruckType
    vehicle_id:     str | None = None
    date:           date
    shift:          Literal[1, 2] = 1

    ordered_stops:  list[DeliveryStop]

    # Metrics
    total_distance_km:   float = 0.0
    total_time_min:      float = 0.0
    total_stops:         int   = 0
    total_invoice_value: Decimal = Decimal("0")
    total_cash_to_collect: Decimal = Decimal("0")

    # Quality flags
    time_window_violations: list[str] = []  # customer_ids with violations
    has_tight_windows:      bool = False    # any window ≤ 30 min

    # vs historical baseline (if available)
    baseline_distance_km: float | None = None
    distance_improvement_pct: float | None = None

    # AI explanation (optional, from Gemini)
    explanation: str | None = None


class OptimizationResult(BaseModel):
    """
    Combined output of /optimize/full.
    Everything the frontend needs in one payload.
    """
    job_id:         str          # UUID — used to subscribe to WS updates
    transport_id:   str
    status:         Literal["pending", "running", "done", "error"]
    created_at:     datetime
    completed_at:   datetime | None = None

    route:          RouteResult | None = None
    load:           LoadPlan    | None = None

    # Frontend visualization payload
    viz:            TruckVisualization | None = None

    error_message:  str | None = None


class TruckVisualization(BaseModel):
    """
    Structured data for the frontend 3D truck renderer.
    Coordinate origin: front-left-floor corner of truck cargo area.
    x = truck length (0=front door side), y = truck width, z = height.
    """
    truck_dims: dict = Field(
        default={"length_cm": 620, "width_cm": 240, "height_cm": 240}
    )
    pallet_dims: dict = Field(
        default={"length_cm": 120, "width_cm": 80, "height_cm": 15}
    )
    pallets: list[VizPallet] = []
    route_geojson: dict | None = None   # GeoJSON LineString for map


class VizPallet(BaseModel):
    pallet_id:   str
    label:       str     # e.g. "Stop 3 – Bar El Tupí"
    color:       str     # hex, e.g. "#3b82f6" — one color per stop
    position:    dict    # {"x": 0, "y": 0, "z": 0} in cm from origin
    dims:        dict    # {"l": 120, "w": 80, "h": 140}
    is_return:   bool = False
    stop_ids:    list[str] = []
    products_summary: list[str] = []  # ["114× ED13", "4× ED30"]
```

---

## 2. Request / Response Schemas (`models/schemas.py`)

```python
class OptimizeRequest(BaseModel):
    """POST /optimize/full"""
    transport_id: str
    truck_type:   TruckType = TruckType.TRUCK_6
    date:         date | None = None           # defaults to today
    use_real_roads: bool = False               # True = ORS API, False = haversine
    respect_time_windows: bool = True
    include_returnables:  bool = True
    solver_time_limit_s:  int  = Field(default=15, ge=5, le=60)


class TransportSummary(BaseModel):
    """GET /data/routes response item"""
    transport_id:  str
    route_code:    str
    driver_name:   str
    date:          date
    stop_count:    int
    truck_type:    TruckType


class CustomerDetail(BaseModel):
    """GET /data/customers/{id}"""
    customer_id:   str
    name:          str
    address:       str
    city:          str
    postal_code:   str
    lat:           float | None
    lng:           float | None
    time_windows:  dict[int, TimeWindow]  # {weekday(0-4): window}


class HealthResponse(BaseModel):
    status:  Literal["ok"] = "ok"
    data_loaded: bool
    customer_count:  int
    transport_count: int
    geocoded_count:  int
```

---

## 3. WebSocket Protocol

### Why WebSocket?

Route optimization can take 5–30 seconds (OR-Tools with time limit). Rather than
blocking an HTTP request, the frontend subscribes to a job via WebSocket and
receives live progress updates as the optimizer runs each phase.

### Connection Flow

```
Frontend                              Backend
   |                                     |
   |  POST /optimize/full                |
   |  ────────────────────────────────►  |  Returns immediately:
   |  ◄────────────────────────────────  |  { job_id: "abc-123", status: "pending" }
   |                                     |
   |  WS /ws/jobs/abc-123                |
   |  ────────────────────────────────►  |  Upgrade to WebSocket
   |  ◄────────────────────────────────  |  Connected
   |                                     |
   |  ◄─── WsMessage(type="progress") ── |  "Geocoding addresses…" 10%
   |  ◄─── WsMessage(type="progress") ── |  "Building distance matrix…" 25%
   |  ◄─── WsMessage(type="progress") ── |  "Running VRP solver…" 40%
   |  ◄─── WsMessage(type="progress") ── |  "Packing pallets…" 70%
   |  ◄─── WsMessage(type="progress") ── |  "Generating pick list…" 85%
   |  ◄─── WsMessage(type="progress") ── |  "Generating explanation…" 95%
   |  ◄─── WsMessage(type="result")  ──  |  Full OptimizationResult payload
   |  ◄─── WsMessage(type="done")    ──  |  Connection can close
```

### WebSocket Endpoint

```python
# routers/ws.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from services.job_manager import JobManager

router = APIRouter()
job_manager = JobManager()  # in-memory job store

@router.websocket("/ws/jobs/{job_id}")
async def ws_job_updates(websocket: WebSocket, job_id: str):
    await websocket.accept()
    try:
        async for message in job_manager.subscribe(job_id):
            await websocket.send_json(message.model_dump())
            if message.type in ("done", "error"):
                break
    except WebSocketDisconnect:
        pass
    finally:
        await websocket.close()
```

---

### 3.1 WebSocket Message Schema

All messages are JSON with a `type` discriminator field.

```python
from typing import Annotated, Union
from pydantic import Discriminator, Tag


class WsProgress(BaseModel):
    type:       Literal["progress"] = "progress"
    job_id:     str
    phase:      str        # human-readable phase name
    pct:        int        # 0–100
    message:    str        # display string for the frontend spinner
    timestamp:  datetime


class WsPartialResult(BaseModel):
    """Sent as soon as route is done, before load is computed."""
    type:       Literal["partial"] = "partial"
    job_id:     str
    route:      RouteResult
    timestamp:  datetime


class WsResult(BaseModel):
    """Final full payload — everything the frontend needs."""
    type:       Literal["result"] = "result"
    job_id:     str
    result:     OptimizationResult
    timestamp:  datetime


class WsDone(BaseModel):
    type:       Literal["done"] = "done"
    job_id:     str
    timestamp:  datetime


class WsError(BaseModel):
    type:       Literal["error"] = "error"
    job_id:     str
    code:       str    # e.g. "GEOCODING_FAILED", "NO_FEASIBLE_ROUTE"
    message:    str
    timestamp:  datetime


# Union type for type-safe deserialization on frontend
WsMessage = Annotated[
    Union[
        Annotated[WsProgress,      Tag("progress")],
        Annotated[WsPartialResult, Tag("partial")],
        Annotated[WsResult,        Tag("result")],
        Annotated[WsDone,          Tag("done")],
        Annotated[WsError,         Tag("error")],
    ],
    Discriminator("type"),
]
```

---

### 3.2 Progress Phase Definitions

The backend emits these exact phase names in order. Frontend can map them to
UI labels or step indicators.

| Phase key | pct | Message shown to user |
|-----------|-----|-----------------------|
| `geocoding` | 10 | "Geocoding customer addresses…" |
| `distance_matrix` | 25 | "Calculating road distances…" |
| `vrp_solving` | 45 | "Optimising delivery route…" |
| `pallet_packing` | 65 | "Planning truck load configuration…" |
| `pick_list` | 80 | "Generating warehouse pick list…" |
| `visualization` | 90 | "Building 3D visualization…" |
| `explanation` | 95 | "Generating AI explanation…" |
| `done` | 100 | "Optimisation complete" |

---

### 3.3 Job Manager (`services/job_manager.py`)

```python
import asyncio
import uuid
from datetime import datetime
from collections import defaultdict


class JobManager:
    """
    In-memory async job queue. No Redis needed for hackathon.
    Stores up to 50 recent jobs (deque with maxlen).
    """
    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}
        self._results: dict[str, OptimizationResult] = {}

    def create_job(self, transport_id: str) -> str:
        job_id = str(uuid.uuid4())[:8]   # short ID for readability
        self._queues[job_id] = asyncio.Queue()
        return job_id

    async def publish(self, job_id: str, message: WsMessage) -> None:
        if job_id in self._queues:
            await self._queues[job_id].put(message)

    async def subscribe(self, job_id: str):
        """Async generator — yields messages as they arrive."""
        if job_id not in self._queues:
            yield WsError(
                job_id=job_id,
                code="JOB_NOT_FOUND",
                message=f"No job with id {job_id}",
                timestamp=datetime.utcnow(),
            )
            return
        q = self._queues[job_id]
        while True:
            msg = await asyncio.wait_for(q.get(), timeout=120.0)
            yield msg
            if msg.type in ("done", "error"):
                del self._queues[job_id]
                break

    def get_result(self, job_id: str) -> OptimizationResult | None:
        return self._results.get(job_id)
```

---

### 3.4 Optimizer Service Integration

```python
# services/optimizer.py
import asyncio
from services.job_manager import JobManager

async def run_optimization(
    job_id: str,
    request: OptimizeRequest,
    job_manager: JobManager,
    app_data: AppData,
) -> None:
    """
    Runs in a background task (asyncio.create_task).
    Publishes progress messages throughout execution.
    """
    async def progress(phase: str, pct: int, msg: str):
        await job_manager.publish(job_id, WsProgress(
            job_id=job_id, phase=phase, pct=pct,
            message=msg, timestamp=datetime.utcnow()
        ))

    try:
        await progress("geocoding", 10, "Geocoding customer addresses…")
        stops = build_transport(request.transport_id, app_data)
        stops = await geocode_stops(stops)   # async, cached

        await progress("distance_matrix", 25, "Calculating road distances…")
        matrix = build_distance_matrix(stops, use_real_roads=request.use_real_roads)

        await progress("vrp_solving", 45, "Optimising delivery route…")
        route = solve_vrp(stops, request, matrix)

        # Emit partial result — frontend can show the map immediately
        await job_manager.publish(job_id, WsPartialResult(
            job_id=job_id, route=route, timestamp=datetime.utcnow()
        ))

        await progress("pallet_packing", 65, "Planning truck load configuration…")
        load = pack_truck(route.ordered_stops, request)

        await progress("pick_list", 80, "Generating warehouse pick list…")
        load.pick_list = generate_pick_list(load.pallets)

        await progress("visualization", 90, "Building 3D visualization…")
        viz = build_visualization(route, load)

        explanation = None
        if GEMINI_ENABLED:
            await progress("explanation", 95, "Generating AI explanation…")
            explanation = await explain_route(route, load)

        result = OptimizationResult(
            job_id=job_id,
            transport_id=request.transport_id,
            status="done",
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            route=route,
            load=load,
            viz=viz,
        )
        route.explanation = explanation

        await job_manager.publish(job_id, WsResult(
            job_id=job_id, result=result, timestamp=datetime.utcnow()
        ))
        await job_manager.publish(job_id, WsDone(
            job_id=job_id, timestamp=datetime.utcnow()
        ))

    except Exception as e:
        await job_manager.publish(job_id, WsError(
            job_id=job_id,
            code=type(e).__name__.upper(),
            message=str(e),
            timestamp=datetime.utcnow(),
        ))
```

---

### 3.5 Router Wiring (`routers/optimize.py`)

```python
from fastapi import APIRouter, BackgroundTasks

router = APIRouter(prefix="/api/v1")

@router.post("/optimize/full", response_model=dict)
async def optimize_full(
    request: OptimizeRequest,
    background_tasks: BackgroundTasks,
    app_data: AppData = Depends(get_app_data),
    job_manager: JobManager = Depends(get_job_manager),
):
    job_id = job_manager.create_job(request.transport_id)

    background_tasks.add_task(
        run_optimization, job_id, request, job_manager, app_data
    )

    return {
        "job_id": job_id,
        "status": "pending",
        "ws_url": f"/ws/jobs/{job_id}",
    }
```

---

## 4. Frontend Usage Guide

### Connect and handle all message types

```typescript
// TypeScript example for the frontend team

type WsMessage =
  | { type: "progress";  job_id: string; phase: string; pct: number; message: string }
  | { type: "partial";   job_id: string; route: RouteResult }
  | { type: "result";    job_id: string; result: OptimizationResult }
  | { type: "done";      job_id: string }
  | { type: "error";     job_id: string; code: string; message: string }

async function optimizeTransport(transportId: string, truckType: string) {
  // 1. Kick off the job
  const res = await fetch("/api/v1/optimize/full", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ transport_id: transportId, truck_type: truckType }),
  })
  const { job_id, ws_url } = await res.json()

  // 2. Open WebSocket
  const ws = new WebSocket(`ws://localhost:8000${ws_url}`)

  ws.onmessage = (event) => {
    const msg: WsMessage = JSON.parse(event.data)

    switch (msg.type) {
      case "progress":
        updateProgressBar(msg.pct, msg.message)
        break

      case "partial":
        // Route is ready — render the map immediately, load still computing
        renderRouteOnMap(msg.route.ordered_stops)
        break

      case "result":
        // Everything ready
        renderRouteOnMap(msg.result.route.ordered_stops)
        render3DTruck(msg.result.viz)
        renderPickList(msg.result.load.pick_list)
        renderMetrics({
          distance: msg.result.route.total_distance_km,
          improvement: msg.result.route.distance_improvement_pct,
          pallets: msg.result.load.pallet_slots_used,
          violations: msg.result.route.time_window_violations.length,
        })
        if (msg.result.route.explanation) {
          showAiExplanation(msg.result.route.explanation)
        }
        break

      case "error":
        showErrorToast(`${msg.code}: ${msg.message}`)
        break

      case "done":
        ws.close()
        break
    }
  }
}
```

---

## 5. Error Codes Reference

| Code | Trigger | Frontend action |
|------|---------|-----------------|
| `JOB_NOT_FOUND` | WS connected with unknown job_id | Show "session expired" |
| `TRANSPORT_NOT_FOUND` | transport_id not in dataset | Show form validation error |
| `GEOCODING_FAILED` | All geocoding attempts failed | Show warning, use fallback coords |
| `NO_FEASIBLE_ROUTE` | VRP solver finds no solution | Show "reduce constraints" hint |
| `PACKING_OVERFLOW` | Products exceed truck capacity | Show capacity alert |
| `SOLVER_TIMEOUT` | VRP hit time limit with no solution | Return best found or error |
| `GEMINI_ERROR` | Gemini API unavailable | Skip explanation silently |

---

## 6. Key Design Decisions

**Single POST → WS pattern** rather than polling: gives the frontend a real-time
progress bar without hammering the API. The POST returns immediately with a
`job_id`; the heavy work runs in a `BackgroundTask`.

**Partial result after route phase**: the frontend can render the map and
animate the route while pallet packing is still running. This makes the
experience feel faster.

**`job_id` is 8-char UUID prefix** (e.g. `"a3f2b1c8"`): short enough to display
in URLs or logs, unique enough for a hackathon with < 100 concurrent sessions.

**In-memory JobManager**: no Redis, no database. Works perfectly for a single-
server hackathon demo. The `asyncio.Queue` is non-blocking so the WebSocket
handler never stalls the event loop.

**`TruckVisualization` is frontend-agnostic**: the backend doesn't know whether
the frontend uses Three.js, Babylon.js, or CSS 3D — it just sends coordinates
and dimensions in centimetres. The frontend owns the rendering.
