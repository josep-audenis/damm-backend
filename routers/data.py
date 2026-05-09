from fastapi import APIRouter, HTTPException

from models.schemas import (
    CustomerDetail,
    HealthResponse,
    RouteSummary,
    TransportDetail,
    TransportSummary,
)
from services.data_loader import repository


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
