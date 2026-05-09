from fastapi import APIRouter, BackgroundTasks, HTTPException

from models.schemas import OptimizeAcceptedResponse, OptimizeRequest, OptimizationResultResponse
from services.db_repository import repository
from services.job_manager import job_manager
from services.optimization import optimization_service


router = APIRouter(prefix="/api/v1/optimize", tags=["optimize"])


@router.post("/full", response_model=OptimizeAcceptedResponse)
def optimize_full(request: OptimizeRequest, background_tasks: BackgroundTasks) -> OptimizeAcceptedResponse:
    job_id = job_manager.create_job(request)
    background_tasks.add_task(job_manager.run_job, job_id)
    return OptimizeAcceptedResponse(job_id=job_id, ws_url=f"/ws/jobs/{job_id}")


@router.post("/full/preview", response_model=OptimizationResultResponse)
async def optimize_full_preview(request: OptimizeRequest) -> OptimizationResultResponse:
    if request.transport_id is None:
        request = request.model_copy(update={"persist_plan": False})
        result = await optimization_service.optimize_orders(request)
        return OptimizationResultResponse(result=result)
    transport = repository.get_transport(request.transport_id)
    if transport is None:
        raise HTTPException(status_code=404, detail="Transport not found")
    result = optimization_service.optimize(transport, request)
    return OptimizationResultResponse(result=result)
