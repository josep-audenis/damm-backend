from __future__ import annotations

from datetime import date as DateType
from datetime import datetime as DateTimeType
from typing import Literal

from pydantic import BaseModel, Field

from models.domain import (
    DeliveryStop,
    OptimizationResult,
    RouteResult,
    TimeWindow,
    TruckType,
)


class OptimizeRequest(BaseModel):
    transport_id: str | None = None
    date: DateType | None = None
    date_range_days: int = Field(default=1, ge=1, le=14, description="Include orders from date up to date+N days")
    warehouse_id: str | None = None
    truck_ids: list[str] | None = None
    persist_plan: bool = True
    max_orders: int = Field(default=500, ge=1, le=5000)
    truck_type: TruckType = TruckType.TRUCK_6
    use_real_roads: bool = False
    respect_time_windows: bool = False
    include_returnables: bool = True
    solver_time_limit_s: int = Field(default=30, ge=5, le=120)


class OptimizeAcceptedResponse(BaseModel):
    job_id: str
    status: Literal["pending"] = "pending"
    ws_url: str


class TransportSummary(BaseModel):
    transport_id: str
    route_code: str
    driver_name: str
    date: DateType
    stop_count: int
    truck_type: TruckType


class RouteSummary(BaseModel):
    route_code: str
    transport_count: int
    stop_count: int


class TransportDetail(BaseModel):
    transport_id: str
    route_code: str
    driver_id: str
    driver_name: str
    date: DateType
    truck_type: TruckType
    capacity_pallets: int | None = None
    stops: list[DeliveryStop] = Field(default_factory=list)


class CustomerDetail(BaseModel):
    customer_id: str
    name: str
    address: str
    city: str
    postal_code: str
    lat: float | None = None
    lng: float | None = None
    time_windows: dict[int, TimeWindow] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    data_loaded: bool
    customer_count: int
    transport_count: int
    geocoded_count: int


class OrderImportRowError(BaseModel):
    row: int
    reason: str
    raw: dict[str, str] = Field(default_factory=dict)


class OrderImportResponse(BaseModel):
    status: Literal["ok"] = "ok"
    received: int
    inserted: int
    skipped: int
    unknown_customers: list[str] = Field(default_factory=list)
    unknown_materials: list[str] = Field(default_factory=list)
    errors: list[OrderImportRowError] = Field(default_factory=list)


class ClearImportedOrdersResponse(BaseModel):
    status: Literal["ok"] = "ok"
    deleted_orders: int
    deleted_delivery_lines: int


class RoutePreviewResponse(BaseModel):
    route: RouteResult


class OptimizationResultResponse(BaseModel):
    result: OptimizationResult


class PersistRouteRequest(BaseModel):
    route: RouteResult
    # Used to scope truck resolution so a 6pal truck from another warehouse
    # isn't picked. Optional — when omitted, we pick any matching truck.
    warehouse_id: str | None = None


class PersistRouteResponse(BaseModel):
    status: Literal["ok"] = "ok"
    transport_id: str
    stops_inserted: int
    resolved_driver_id: str | None = None
    resolved_truck_id: str | None = None
    resolved_route_id: str | None = None


class WsProgress(BaseModel):
    type: Literal["progress"] = "progress"
    job_id: str
    phase: str
    pct: int
    message: str
    timestamp: DateTimeType


class WsPartialResult(BaseModel):
    type: Literal["partial"] = "partial"
    job_id: str
    route: RouteResult
    timestamp: DateTimeType


class WsResult(BaseModel):
    type: Literal["result"] = "result"
    job_id: str
    result: OptimizationResult
    timestamp: DateTimeType


class WsDone(BaseModel):
    type: Literal["done"] = "done"
    job_id: str
    timestamp: DateTimeType


class WsError(BaseModel):
    type: Literal["error"] = "error"
    job_id: str
    code: str
    message: str
    timestamp: DateTimeType
