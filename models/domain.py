from __future__ import annotations

from datetime import date as DateType
from datetime import datetime as DateTimeType
from datetime import time as TimeType
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


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


class TimeWindow(BaseModel):
    open: TimeType
    close: TimeType


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
    warehouse_location: str | None = None
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
    estimated_arrival: TimeType | None = None
    products: list[ProductLine] = Field(default_factory=list)
    returnables: list[ReturnableItem] = Field(default_factory=list)
    payment_condition: PaymentCondition = PaymentCondition.CREDITO
    invoice_total: Decimal | None = None
    cash_to_collect: Decimal = Decimal("0")
    albaran_numbers: list[str] = Field(default_factory=list)
    travel_time_from_prev_min: float | None = None
    distance_from_prev_km: float | None = None


class PalletItem(BaseModel):
    product: ProductLine
    layer: int
    column: int
    stack_height_cm: float


class Pallet(BaseModel):
    pallet_index: int
    pallet_id: str
    stop_ids: list[str] = Field(default_factory=list)
    is_returnables: bool = False
    items: list[PalletItem] = Field(default_factory=list)
    products_summary: list[str] = Field(default_factory=list)
    total_height_cm: float = 0.0
    total_weight_kg: float = 0.0
    total_volume_l: float = 0.0
    position_in_truck: dict[str, float] = Field(default_factory=dict)


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
    date: DateType
    pallets: list[Pallet] = Field(default_factory=list)
    pick_list: list[PickInstruction] = Field(default_factory=list)
    items_no_location: list[ProductLine] = Field(default_factory=list)
    return_pallet: Pallet | None = None
    total_units_delivery: int = 0
    total_units_return: int = 0
    total_volume_delivery_l: float = 0.0
    total_volume_return_l: float = 0.0
    total_weight_delivery_kg: float = 0.0
    total_weight_return_kg: float = 0.0
    pallet_slots_used: int = 0
    pallet_slots_total: int = 0


class RouteResult(BaseModel):
    transport_id: str
    route_code: str
    driver_id: str
    driver_name: str
    truck_type: TruckType
    vehicle_id: str | None = None
    date: DateType
    shift: Literal[1, 2] = 1
    ordered_stops: list[DeliveryStop] = Field(default_factory=list)
    total_distance_km: float = 0.0
    total_time_min: float = 0.0
    total_stops: int = 0
    total_invoice_value: Decimal = Decimal("0")
    total_cash_to_collect: Decimal = Decimal("0")
    time_window_violations: list[str] = Field(default_factory=list)
    has_tight_windows: bool = False
    baseline_distance_km: float | None = None
    distance_improvement_pct: float | None = None
    explanation: str | None = None
    route_geojson: dict | None = None


class VizPallet(BaseModel):
    pallet_id: str
    label: str
    color: str
    position: dict[str, float]
    dims: dict[str, float]
    is_return: bool = False
    stop_ids: list[str] = Field(default_factory=list)
    products_summary: list[str] = Field(default_factory=list)


class TruckVisualization(BaseModel):
    truck_dims: dict[str, float] = Field(
        default_factory=lambda: {"length_cm": 620, "width_cm": 240, "height_cm": 240}
    )
    pallet_dims: dict[str, float] = Field(
        default_factory=lambda: {"length_cm": 120, "width_cm": 80, "height_cm": 15}
    )
    pallets: list[VizPallet] = Field(default_factory=list)
    route_geojson: dict | None = None


class TruckSlot(BaseModel):
    column: Literal["left", "right"]
    row: int
    pallet_id: str
    stop_id: str
    customer_name: str
    sequence: int
    products: list[ProductLine] = Field(default_factory=list)
    volume_units: float = 0.0
    is_empty: bool = False


class TruckLayout(BaseModel):
    truck_type: TruckType
    rows: int
    columns: int = 2
    left: list[TruckSlot] = Field(default_factory=list)
    right: list[TruckSlot] = Field(default_factory=list)
    total_slots: int = 0
    used_slots: int = 0


class OptimizationResult(BaseModel):
    job_id: str
    transport_id: str
    status: Literal["pending", "running", "done", "error"]
    created_at: DateTimeType
    completed_at: DateTimeType | None = None
    route: RouteResult | None = None
    routes: list[RouteResult] = Field(default_factory=list)
    load: LoadPlan | None = None
    loads: list[LoadPlan] = Field(default_factory=list)
    viz: TruckVisualization | None = None
    truck_layout: TruckLayout | None = None
    truck_layouts: list[TruckLayout] = Field(default_factory=list)
    error_message: str | None = None
