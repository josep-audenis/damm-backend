# Data Models Contract

This page is the shared model contract between backend and frontend. The content may evolve, but field names, enum values, and message types must not change silently.

The models are derived from DDI operational documents:

- Hoja Carga: warehouse pick/load sheet.
- Hoja Ruta: driver route sheet.
- Albaran: delivery invoice.

## Backend File Targets

```txt
app/domain/models.py
app/domain/enums.py
app/api/schemas.py
```

## Frontend File Targets

```txt
lib/schemas/domain.ts
lib/schemas/ws.ts
lib/api/generated.ts
```

## Enums

```python
class TruckType(str, Enum):
    TRUCK_6 = "6pal"
    TRUCK_8 = "8pal"
    VAN = "van"

class PaymentCondition(str, Enum):
    CONTADO = "CONTADO"
    CREDITO = "CREDITO"

class ProductUnit(str, Enum):
    CAJ = "CAJ"
    PAL = "PAL"
    UN = "UN"
    BOT = "BOT"
    BRL = "BRL"
    TUB = "TUB"
    PAK = "PAK"
    TB = "TB"
    EST = "EST"
    PQ = "PQ"
    TIR = "TIR"
    BID = "BID"
    ZPR = "ZPR"

class ProductCategory(str, Enum):
    BEER_BOTTLE = "beer_bottle"
    BEER_BARREL = "beer_barrel"
    WATER = "water"
    SOFT_DRINK = "soft_drink"
    DAIRY = "dairy"
    COFFEE = "coffee"
    WINE_SPIRITS = "wine_spirits"
    FOOD = "food"
    DISPOSABLE = "disposable"
    MERCHANDISE = "merchandise"
    GAS = "gas"
    RETURNABLE_EMPTY = "returnable_empty"
```

## Primitive Models

```python
class TimeWindow(BaseModel):
    open: time
    close: time

    @property
    def duration_minutes(self) -> int:
        open_minutes = self.open.hour * 60 + self.open.minute
        close_minutes = self.close.hour * 60 + self.close.minute
        return close_minutes - open_minutes

    def is_tight(self) -> bool:
        return self.duration_minutes <= 30
```

## Product Models

```python
class ProductDimensions(BaseModel):
    length_cm: float = 40.0
    width_cm: float = 30.0
    height_cm: float = 25.0
    volume_l: float | None = None
    weight_gross_kg: float = 15.0
    weight_net_kg: float | None = None

class ProductLine(BaseModel):
    material_code: str
    description: str
    quantity: int
    unit: ProductUnit
    category: ProductCategory
    is_returnable: bool
    warehouse_location: str | None
    dimensions: ProductDimensions | None = None
    unit_price: Decimal | None = None
    discount_pct: Decimal | None = None
    net_amount: Decimal | None = None
    vat_rate: Decimal | None = None

class ReturnableItem(BaseModel):
    material_code: str
    description: str
    quantity: int
    unit: ProductUnit
    volume_l: float | None = None
    weight_kg: float | None = None
```

## Delivery Models

```python
class DeliveryStop(BaseModel):
    stop_id: str
    sequence: int
    customer_id: str
    customer_name: str
    address: str
    postal_code: str
    city: str
    lat: float | None = None
    lng: float | None = None
    time_window: TimeWindow | None = None
    shift: Literal[1, 2] = 1
    estimated_arrival: time | None = None
    products: list[ProductLine] = []
    returnables: list[ReturnableItem] = []
    payment_condition: PaymentCondition = PaymentCondition.CREDITO
    invoice_total: Decimal | None = None
    cash_to_collect: Decimal = Decimal("0")
    albaran_numbers: list[str] = []
    travel_time_from_prev_min: float | None = None
    distance_from_prev_km: float | None = None
```

## Pallet And Load Models

```python
class PalletItem(BaseModel):
    product: ProductLine
    layer: int
    column: int
    stack_height_cm: float

class Pallet(BaseModel):
    pallet_index: int
    pallet_id: str
    stop_ids: list[str]
    is_returnables: bool = False
    items: list[PalletItem] = []
    total_height_cm: float = 0.0
    total_weight_kg: float = 0.0
    total_volume_l: float = 0.0
    position_in_truck: dict = Field(default_factory=dict)

class PickInstruction(BaseModel):
    sequence: int
    warehouse_location: str
    material_code: str
    description: str
    quantity: int
    unit: ProductUnit
    pallet_id: str
    stop_id: str

class LoadPlan(BaseModel):
    transport_id: str
    truck_type: TruckType
    vehicle_id: str | None = None
    date: date
    pallets: list[Pallet]
    pick_list: list[PickInstruction]
    items_no_location: list[ProductLine] = []
    return_pallet: Pallet | None = None
    total_units_delivery: int = 0
    total_units_return: int = 0
    total_volume_delivery_l: float = 0.0
    total_volume_return_l: float = 0.0
    total_weight_delivery_kg: float = 0.0
    total_weight_return_kg: float = 0.0
    pallet_slots_used: int = 0
    pallet_slots_total: int = 0

    @property
    def utilization_pct(self) -> float:
        if self.pallet_slots_total == 0:
            return 0.0
        return round(self.pallet_slots_used / self.pallet_slots_total * 100, 1)
```

## Route And Optimization Models

```python
class RouteResult(BaseModel):
    transport_id: str
    route_code: str
    driver_id: str
    driver_name: str
    truck_type: TruckType
    vehicle_id: str | None = None
    date: date
    shift: Literal[1, 2] = 1
    ordered_stops: list[DeliveryStop]
    total_distance_km: float = 0.0
    total_time_min: float = 0.0
    total_stops: int = 0
    total_invoice_value: Decimal = Decimal("0")
    total_cash_to_collect: Decimal = Decimal("0")
    time_window_violations: list[str] = []
    has_tight_windows: bool = False
    baseline_distance_km: float | None = None
    distance_improvement_pct: float | None = None
    explanation: str | None = None

class OptimizationResult(BaseModel):
    job_id: str
    transport_id: str
    status: Literal["pending", "running", "done", "error"]
    created_at: datetime
    completed_at: datetime | None = None
    route: RouteResult | None = None
    load: LoadPlan | None = None
    viz: TruckVisualization | None = None
    error_message: str | None = None
```

## Visualization Models

```python
class TruckVisualization(BaseModel):
    truck_dims: dict = Field(default={"length_cm": 620, "width_cm": 240, "height_cm": 240})
    pallet_dims: dict = Field(default={"length_cm": 120, "width_cm": 80, "height_cm": 15})
    pallets: list[VizPallet] = []
    route_geojson: dict | None = None

class VizPallet(BaseModel):
    pallet_id: str
    label: str
    color: str
    position: dict
    dims: dict
    is_return: bool = False
    stop_ids: list[str] = []
    products_summary: list[str] = []
```

Coordinate convention:

```txt
Origin: front-left-floor corner of truck cargo area.
x = truck length, 0 means front.
y = truck width.
z = height.
Units are centimeters.
```

## Request / Response Schemas

```python
class OptimizeRequest(BaseModel):
    transport_id: str
    truck_type: TruckType = TruckType.TRUCK_6
    date: date | None = None
    use_real_roads: bool = False
    respect_time_windows: bool = True
    include_returnables: bool = True
    solver_time_limit_s: int = Field(default=15, ge=5, le=60)

class TransportSummary(BaseModel):
    transport_id: str
    route_code: str
    driver_name: str
    date: date
    stop_count: int
    truck_type: TruckType

class RouteSummary(BaseModel):
    route_code: str
    transport_count: int
    stop_count: int

class CustomerDetail(BaseModel):
    customer_id: str
    name: str
    address: str
    city: str
    postal_code: str
    lat: float | None
    lng: float | None
    time_windows: dict[int, TimeWindow]

class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    data_loaded: bool
    customer_count: int
    transport_count: int
    geocoded_count: int
```

## WebSocket Message Models

```python
class WsProgress(BaseModel):
    type: Literal["progress"] = "progress"
    job_id: str
    phase: str
    pct: int
    message: str
    timestamp: datetime

class WsPartialResult(BaseModel):
    type: Literal["partial"] = "partial"
    job_id: str
    route: RouteResult
    timestamp: datetime

class WsResult(BaseModel):
    type: Literal["result"] = "result"
    job_id: str
    result: OptimizationResult
    timestamp: datetime

class WsDone(BaseModel):
    type: Literal["done"] = "done"
    job_id: str
    timestamp: datetime

class WsError(BaseModel):
    type: Literal["error"] = "error"
    job_id: str
    code: str
    message: str
    timestamp: datetime
```

Frontend discriminated union:

```ts
type WsMessage =
  | { type: "progress"; job_id: string; phase: string; pct: number; message: string; timestamp: string }
  | { type: "partial"; job_id: string; route: RouteResult; timestamp: string }
  | { type: "result"; job_id: string; result: OptimizationResult; timestamp: string }
  | { type: "done"; job_id: string; timestamp: string }
  | { type: "error"; job_id: string; code: string; message: string; timestamp: string }
```

## Evolution Rule

Adding optional fields is allowed.

Renaming fields, changing enum values, changing endpoint paths, or changing WebSocket message `type` values requires a contract proposal in `wiki/decisions/`.
