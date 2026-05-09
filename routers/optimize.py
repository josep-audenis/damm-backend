from datetime import date, datetime, time
from uuid import uuid4

from fastapi import APIRouter

from models.domain import (
    DeliveryStop,
    LoadPlan,
    OptimizationResult,
    Pallet,
    PaymentCondition,
    PickInstruction,
    ProductCategory,
    ProductDimensions,
    ProductLine,
    ProductUnit,
    RouteResult,
    TimeWindow,
    TruckType,
    TruckVisualization,
    VizPallet,
)
from models.schemas import OptimizeAcceptedResponse, OptimizeRequest, OptimizationResultResponse


router = APIRouter(prefix="/api/v1/optimize", tags=["optimize"])


def _sample_stop() -> DeliveryStop:
    return DeliveryStop(
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
        payment_condition=PaymentCondition.CREDITO,
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
    )


@router.post("/full", response_model=OptimizeAcceptedResponse)
def optimize_full(request: OptimizeRequest) -> OptimizeAcceptedResponse:
    job_id = uuid4().hex[:8]
    return OptimizeAcceptedResponse(job_id=job_id, ws_url=f"/ws/jobs/{job_id}")


@router.post("/full/preview", response_model=OptimizationResultResponse)
def optimize_full_preview(request: OptimizeRequest) -> OptimizationResultResponse:
    stop = _sample_stop()
    route = RouteResult(
        transport_id=request.transport_id,
        route_code="DR0006",
        driver_id="850006",
        driver_name="JOSE VELEZ",
        truck_type=request.truck_type,
        date=request.date or date(2026, 1, 30),
        ordered_stops=[stop],
        total_distance_km=4.2,
        total_time_min=18.0,
        total_stops=1,
        has_tight_windows=False,
    )
    load = LoadPlan(
        transport_id=request.transport_id,
        truck_type=request.truck_type,
        date=request.date or date(2026, 1, 30),
        pallets=[Pallet(pallet_index=0, pallet_id="PAL-001", stop_ids=[stop.stop_id])],
        pick_list=[
            PickInstruction(
                sequence=1,
                warehouse_location="FA05A2",
                material_code="ED13",
                description="ESTRELLA DAMM 1/3 RET",
                quantity=2,
                unit=ProductUnit.CAJ,
                pallet_id="PAL-001",
                stop_id=stop.stop_id,
            )
        ],
        pallet_slots_used=1,
        pallet_slots_total=6 if request.truck_type == TruckType.TRUCK_6 else 8,
    )
    viz = TruckVisualization(
        pallets=[
            VizPallet(
                pallet_id="PAL-001",
                label="Stop 1 - Bar Granada",
                color="#3b82f6",
                position={"x": 0, "y": 0, "z": 0},
                dims={"l": 120, "w": 80, "h": 120},
                stop_ids=[stop.stop_id],
                products_summary=["2x ED13"],
            )
        ]
    )
    result = OptimizationResult(
        job_id=uuid4().hex[:8],
        transport_id=request.transport_id,
        status="done",
        created_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        route=route,
        load=load,
        viz=viz,
    )
    return OptimizationResultResponse(result=result)
