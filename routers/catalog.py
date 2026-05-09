from fastapi import APIRouter

from models.catalog import (
    BootstrapResponse,
    CustomerCreate,
    CustomerRead,
    MaterialCreate,
    MaterialRead,
    MaterialTypeCreate,
    MaterialTypeRead,
    SourceDocumentRead,
    TruckCreate,
    TruckRead,
    WarehouseCreate,
    WarehouseRead,
)
from services.database import db_service


router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])


@router.post("/bootstrap", response_model=BootstrapResponse)
def bootstrap_catalog() -> BootstrapResponse:
    return BootstrapResponse(counts=db_service.bootstrap_from_excels())


@router.get("/warehouses", response_model=list[WarehouseRead])
def list_warehouses() -> list[WarehouseRead]:
    return [WarehouseRead(**row) for row in db_service.list_rows("warehouses")]


@router.post("/warehouses", response_model=WarehouseRead)
def create_warehouse(payload: WarehouseCreate) -> WarehouseRead:
    return WarehouseRead(**db_service.insert_row("warehouses", payload.model_dump()))


@router.get("/trucks", response_model=list[TruckRead])
def list_trucks() -> list[TruckRead]:
    return [TruckRead(**row) for row in db_service.list_rows("trucks")]


@router.post("/trucks", response_model=TruckRead)
def create_truck(payload: TruckCreate) -> TruckRead:
    data = payload.model_dump()
    data["active"] = int(data["active"])
    return TruckRead(**db_service.insert_row("trucks", data))


@router.get("/material-types", response_model=list[MaterialTypeRead])
def list_material_types() -> list[MaterialTypeRead]:
    return [MaterialTypeRead(**row) for row in db_service.list_rows("material_types")]


@router.post("/material-types", response_model=MaterialTypeRead)
def create_material_type(payload: MaterialTypeCreate) -> MaterialTypeRead:
    return MaterialTypeRead(**db_service.insert_row("material_types", payload.model_dump()))


@router.get("/materials", response_model=list[MaterialRead])
def list_materials() -> list[MaterialRead]:
    return [MaterialRead(**row) for row in db_service.list_rows("materials")]


@router.post("/materials", response_model=MaterialRead)
def create_material(payload: MaterialCreate) -> MaterialRead:
    data = payload.model_dump()
    data["is_returnable"] = int(data["is_returnable"])
    return MaterialRead(**db_service.insert_row("materials", data))


@router.get("/customers", response_model=list[CustomerRead])
def list_customers() -> list[CustomerRead]:
    return [CustomerRead(**row) for row in db_service.list_rows("customers")]


@router.post("/customers", response_model=CustomerRead)
def create_customer(payload: CustomerCreate) -> CustomerRead:
    return CustomerRead(**db_service.insert_row("customers", payload.model_dump()))


@router.get("/documents", response_model=list[SourceDocumentRead])
def list_documents() -> list[SourceDocumentRead]:
    return [SourceDocumentRead(**row) for row in db_service.list_rows("source_documents")]
