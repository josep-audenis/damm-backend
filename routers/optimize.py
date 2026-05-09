from uuid import uuid4

from fastapi import APIRouter, HTTPException

from models.schemas import OptimizeAcceptedResponse, OptimizeRequest, OptimizationResultResponse
from services.data_loader import repository
from services.optimization import optimization_service


router = APIRouter(prefix="/api/v1/optimize", tags=["optimize"])


@router.post("/full", response_model=OptimizeAcceptedResponse)
def optimize_full(request: OptimizeRequest) -> OptimizeAcceptedResponse:
    job_id = uuid4().hex[:8]
    return OptimizeAcceptedResponse(job_id=job_id, ws_url=f"/ws/jobs/{job_id}")


@router.post("/full/preview", response_model=OptimizationResultResponse)
def optimize_full_preview(request: OptimizeRequest) -> OptimizationResultResponse:
    transport = repository.get_transport(request.transport_id)
    if transport is None:
        raise HTTPException(status_code=404, detail="Transport not found")
    result = optimization_service.optimize(transport, request)
    return OptimizationResultResponse(result=result)
