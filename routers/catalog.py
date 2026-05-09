from fastapi import APIRouter

from models.catalog import (
    CustomerCreate,
    CustomerRead,
    GeocodeBatchResponse,
    MaterialCreate,
    MaterialRead,
    MaterialTypeCreate,
    MaterialTypeRead,
    TruckCreate,
    TruckRead,
    WarehouseCreate,
    WarehouseRead,
)
from services.db_provider import db_service
from services.geocoding import geocode_location


router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])


@router.get("/warehouses", response_model=list[WarehouseRead])
def list_warehouses() -> list[WarehouseRead]:
    return [WarehouseRead(**row) for row in db_service.list_rows("warehouses")]


@router.post("/warehouses", response_model=WarehouseRead)
async def create_warehouse(payload: WarehouseCreate) -> WarehouseRead:
    data = payload.model_dump()
    if data.get("lat") is None or data.get("lng") is None:
        coordinates = await geocode_location(data)
        if coordinates is not None:
            data["lat"] = coordinates.lat
            data["lng"] = coordinates.lng
    return WarehouseRead(**db_service.insert_row("warehouses", data))


@router.post("/warehouses/geocode-missing", response_model=GeocodeBatchResponse)
async def geocode_missing_warehouses(limit: int = 25) -> GeocodeBatchResponse:
    warehouses = [
        row
        for row in db_service.list_rows("warehouses", limit=1000000)
        if row.get("lat") is None or row.get("lng") is None
    ][:limit]

    updated = 0
    failed = 0
    for warehouse in warehouses:
        coordinates = await geocode_location(warehouse)
        if coordinates is None:
            failed += 1
            continue
        db_service.update_row(
            "warehouses",
            warehouse["id"],
            {"lat": coordinates.lat, "lng": coordinates.lng},
        )
        updated += 1

    return GeocodeBatchResponse(processed=len(warehouses), updated=updated, failed=failed)


@router.get("/trucks", response_model=list[TruckRead])
def list_trucks() -> list[TruckRead]:
    return [TruckRead(**row) for row in db_service.list_rows("trucks")]


@router.post("/trucks", response_model=TruckRead)
def create_truck(payload: TruckCreate) -> TruckRead:
    data = payload.model_dump()
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
async def create_customer(payload: CustomerCreate) -> CustomerRead:
    data = payload.model_dump()
    if data.get("lat") is None or data.get("lng") is None:
        coordinates = await geocode_location(data)
        if coordinates is not None:
            data["lat"] = coordinates.lat
            data["lng"] = coordinates.lng
    return CustomerRead(**db_service.insert_row("customers", data))


@router.post("/customers/geocode-missing", response_model=GeocodeBatchResponse)
async def geocode_missing_customers(limit: int = 25) -> GeocodeBatchResponse:
    customers = [
        row
        for row in db_service.list_rows("customers", limit=1000000)
        if row.get("lat") is None or row.get("lng") is None
    ][:limit]

    updated = 0
    failed = 0
    for customer in customers:
        coordinates = await geocode_location(customer, use_fallbacks=False)
        if coordinates is None:
            failed += 1
            continue
        patch = {"lat": coordinates.lat, "lng": coordinates.lng}
        db_service.update_row("customers", customer["id"], patch)
        db_service.update_rows_by_field("delivery_stops", "customer_id", customer["id"], patch)
        updated += 1

    return GeocodeBatchResponse(processed=len(customers), updated=updated, failed=failed)
