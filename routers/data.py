from datetime import date

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from models.schemas import (
    ClearImportedOrdersResponse,
    CustomerDetail,
    HealthResponse,
    OrderImportResponse,
    OrderImportRowError,
    RouteSummary,
    TransportDetail,
    TransportSummary,
)
from services.db_repository import repository
from services.order_import import order_importer


router = APIRouter(prefix="/api/v1/data", tags=["data"])


@router.get("/health", response_model=HealthResponse)
def data_health() -> HealthResponse:
    return HealthResponse(**repository.health())


@router.get("/routes", response_model=list[RouteSummary])
def list_routes() -> list[RouteSummary]:
    return repository.list_routes()


@router.get("/transports", response_model=list[TransportSummary])
def list_transports() -> list[TransportSummary]:
    return repository.list_transports()


@router.get("/transport/{transport_id}", response_model=TransportDetail)
def get_transport(transport_id: str) -> TransportDetail:
    transport = repository.get_transport(transport_id)
    if transport is None:
        raise HTTPException(status_code=404, detail="Transport not found")
    return transport


@router.get("/customers/{customer_id}", response_model=CustomerDetail)
def get_customer(customer_id: str) -> CustomerDetail:
    customer = repository.get_customer(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.post("/orders/import", response_model=OrderImportResponse)
async def import_orders_csv(
    file: UploadFile = File(..., description="CSV file with new orders."),
    due_date: date | None = Form(default=None),
) -> OrderImportResponse:
    if file.content_type and "csv" not in file.content_type and "text" not in file.content_type:
        raise HTTPException(status_code=400, detail="Upload must be a CSV file")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty CSV upload")

    try:
        summary = order_importer.import_csv(content, due_date=due_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return OrderImportResponse(
        received=summary.received,
        inserted=summary.inserted,
        skipped=summary.skipped,
        unknown_customers=summary.unknown_customers,
        unknown_materials=summary.unknown_materials,
        errors=[
            OrderImportRowError(row=err.row, reason=err.reason, raw=err.raw)
            for err in summary.errors[:200]
        ],
    )


@router.delete("/orders/imported", response_model=ClearImportedOrdersResponse)
def clear_imported_orders() -> ClearImportedOrdersResponse:
    summary = order_importer.clear_imported()
    return ClearImportedOrdersResponse(
        deleted_orders=summary.deleted_orders,
        deleted_delivery_lines=summary.deleted_delivery_lines,
    )
