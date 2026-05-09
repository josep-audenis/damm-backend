from datetime import date, time

from fastapi import APIRouter, HTTPException

from models.domain import (
    DeliveryStop,
    PaymentCondition,
    ProductCategory,
    ProductDimensions,
    ProductLine,
    ProductUnit,
    TimeWindow,
    TruckType,
)
from models.schemas import CustomerDetail, HealthResponse, TransportDetail, TransportSummary


router = APIRouter(prefix="/api/v1/data", tags=["data"])


SAMPLE_TRANSPORTS = [
    TransportSummary(
        transport_id="11420379",
        route_code="DR0006",
        driver_name="JOSE VELEZ",
        date=date(2026, 1, 30),
        stop_count=2,
        truck_type=TruckType.TRUCK_6,
    )
]

SAMPLE_TRANSPORT_DETAIL = TransportDetail(
    transport_id="11420379",
    route_code="DR0006",
    driver_id="850006",
    driver_name="JOSE VELEZ",
    date=date(2026, 1, 30),
    truck_type=TruckType.TRUCK_6,
    stops=[
        DeliveryStop(
            stop_id="90123456",
            sequence=1,
            customer_id="91123456",
            customer_name="BAR GRANADA",
            address="C/ Bergueda 14",
            postal_code="08100",
            city="Mollet del Valles",
            lat=41.5409,
            lng=2.2134,
            time_window=TimeWindow(open=time(8, 0), close=time(11, 0)),
            estimated_arrival=time(8, 30),
            products=[
                ProductLine(
                    material_code="ED13",
                    description="ESTRELLA DAMM 1/3 RET",
                    quantity=2,
                    unit=ProductUnit.CAJ,
                    category=ProductCategory.BEER_BOTTLE,
                    is_returnable=True,
                    warehouse_location="FA05A2",
                    dimensions=ProductDimensions(),
                )
            ],
            payment_condition=PaymentCondition.CREDITO,
            albaran_numbers=["828482327"],
        ),
        DeliveryStop(
            stop_id="90123457",
            sequence=2,
            customer_id="91123457",
            customer_name="PIZZA VALLES",
            address="Av. Example 22",
            postal_code="08100",
            city="Mollet del Valles",
            lat=41.5430,
            lng=2.2170,
            time_window=TimeWindow(open=time(9, 0), close=time(9, 15)),
            estimated_arrival=time(9, 5),
            products=[
                ProductLine(
                    material_code="0RF0088",
                    description="SCHWEPPES TONICA LATA SLEEK 24U",
                    quantity=4,
                    unit=ProductUnit.CAJ,
                    category=ProductCategory.SOFT_DRINK,
                    is_returnable=False,
                    warehouse_location="CB06A2",
                    dimensions=ProductDimensions(),
                )
            ],
            payment_condition=PaymentCondition.CONTADO,
        ),
    ],
)

SAMPLE_CUSTOMERS = {
    "91123456": CustomerDetail(
        customer_id="91123456",
        name="BAR GRANADA",
        address="C/ Bergueda 14",
        city="Mollet del Valles",
        postal_code="08100",
        lat=41.5409,
        lng=2.2134,
        time_windows={0: TimeWindow(open=time(8, 0), close=time(11, 0))},
    )
}


@router.get("/health", response_model=HealthResponse)
def data_health() -> HealthResponse:
    return HealthResponse(
        data_loaded=False,
        customer_count=len(SAMPLE_CUSTOMERS),
        transport_count=len(SAMPLE_TRANSPORTS),
        geocoded_count=len(SAMPLE_CUSTOMERS),
    )


@router.get("/transports", response_model=list[TransportSummary])
def list_transports() -> list[TransportSummary]:
    return SAMPLE_TRANSPORTS


@router.get("/transport/{transport_id}", response_model=TransportDetail)
def get_transport(transport_id: str) -> TransportDetail:
    if transport_id != SAMPLE_TRANSPORT_DETAIL.transport_id:
        raise HTTPException(status_code=404, detail="Transport not found")
    return SAMPLE_TRANSPORT_DETAIL


@router.get("/customers/{customer_id}", response_model=CustomerDetail)
def get_customer(customer_id: str) -> CustomerDetail:
    customer = SAMPLE_CUSTOMERS.get(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer
