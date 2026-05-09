from fastapi import APIRouter, HTTPException, WebSocket

from models.domain import OptimizationResult
from services.job_manager import job_manager


router = APIRouter(tags=["jobs"])


@router.websocket("/ws/jobs/{job_id}")
async def job_updates(websocket: WebSocket, job_id: str) -> None:
    await job_manager.subscribe(job_id, websocket)


@router.get("/api/v1/jobs/{job_id}", response_model=OptimizationResult)
def get_job(job_id: str) -> OptimizationResult:
    result = job_manager.get_result(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return result
