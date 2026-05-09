from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class WarehouseBase(BaseModel):
    code: str
    name: str
    storage_center_code: str | None = None
    address: str | None = None
    postal_code: str | None = None
    city: str | None = None


class WarehouseCreate(WarehouseBase):
    pass


class WarehouseRead(WarehouseBase):
    id: int


class TruckBase(BaseModel):
    code: str
    plate: str | None = None
    truck_type: str = "6pal"
    capacity_pallets: int = 6
    warehouse_id: int | None = None
    active: bool = True


class TruckCreate(TruckBase):
    pass


class TruckRead(TruckBase):
    id: int


class MaterialTypeBase(BaseModel):
    code: str
    name: str
    description: str | None = None


class MaterialTypeCreate(MaterialTypeBase):
    pass


class MaterialTypeRead(MaterialTypeBase):
    id: int


class MaterialBase(BaseModel):
    code: str
    description: str
    base_unit: str | None = None
    material_type_id: int | None = None
    manufacturer: str | None = None
    manufacturer_code: str | None = None
    product_hierarchy_code: str | None = None
    is_returnable: bool = False


class MaterialCreate(MaterialBase):
    pass


class MaterialRead(MaterialBase):
    id: int


class CustomerBase(BaseModel):
    code: str
    name: str
    name_2: str | None = None
    address: str | None = None
    postal_code: str | None = None
    city: str | None = None
    payment_condition: str | None = None
    service_notes: str | None = None


class CustomerCreate(CustomerBase):
    pass


class CustomerRead(CustomerBase):
    id: int


class BootstrapResponse(BaseModel):
    status: Literal["ok"] = "ok"
    counts: dict[str, int] = Field(default_factory=dict)


class SourceDocumentRead(BaseModel):
    id: int
    document_number: str
    document_type: str
    customer_code: str | None = None
    transport_code: str | None = None
    route_code: str | None = None
    delivery_date: date | None = None
    payment_condition: str | None = None
    total_amount: float | None = None
    source_file: str | None = None
