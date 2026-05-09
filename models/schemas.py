from __future__ import annotations

from datetime import date as DateType
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
    transport_id: str
    truck_type: TruckType = TruckType.TRUCK_6
    date: DateType | None = None
    use_real_roads: bool = False
    respect_time_windows: bool = True
    include_returnables: bool = True
    solver_time_limit_s: int = Field(default=15, ge=5, le=60)


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


class RoutePreviewResponse(BaseModel):
    route: RouteResult


class OptimizationResultResponse(BaseModel):
    result: OptimizationResult
