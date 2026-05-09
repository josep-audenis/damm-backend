from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class WarehouseBase(BaseModel):
    name: str
    address: str | None = None
    postal_code: str | None = None
    city: str | None = None
    lat: float | None = None
    lng: float | None = None


class WarehouseCreate(WarehouseBase):
    pass


class WarehouseRead(WarehouseBase):
    id: str


class TruckBase(BaseModel):
    plate: str | None = None
    capacity_pallets: int = 6
    warehouse_id: str | None = None


class TruckCreate(TruckBase):
    pass


class TruckRead(TruckBase):
    id: str


class MaterialTypeBase(BaseModel):
    name: str
    description: str | None = None


class MaterialTypeCreate(MaterialTypeBase):
    pass


class MaterialTypeRead(MaterialTypeBase):
    id: str


class MaterialBase(BaseModel):
    description: str
    base_unit: str | None = None
    material_type_id: str | None = None
    is_returnable: bool = False


class MaterialCreate(MaterialBase):
    pass


class MaterialRead(MaterialBase):
    id: str


class CustomerBase(BaseModel):
    name: str
    name_2: str | None = None
    address: str | None = None
    postal_code: str | None = None
    city: str | None = None
    lat: float | None = None
    lng: float | None = None


class CustomerCreate(CustomerBase):
    pass


class CustomerRead(CustomerBase):
    id: str


class BootstrapResponse(BaseModel):
    status: Literal["ok"] = "ok"
    counts: dict[str, int] = Field(default_factory=dict)


class GeocodeBatchResponse(BaseModel):
    status: Literal["ok"] = "ok"
    processed: int
    updated: int
    failed: int
