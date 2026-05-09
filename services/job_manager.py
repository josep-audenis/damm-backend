from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import WebSocket

from models.domain import OptimizationResult
from models.schemas import (
    OptimizeRequest,
    WsDone,
    WsError,
    WsPartialResult,
    WsProgress,
    WsResult,
)
from services.data_loader import repository
from services.coordinates import enrich_stops_from_local_coordinates, enrich_stops_with_geocoding
from services.optimization import (
    apply_route,
    build_distance_time_matrix,
    build_load_plan,
    build_route_result,
    build_truck_visualization,
    group_stops_by_customer,
    solve_route,
)
from services.road_routing import build_road_matrix, build_route_geojson


WsMessage = WsProgress | WsPartialResult | WsResult | WsDone | WsError


class JobRecord:
    def __init__(self, job_id: str, request: OptimizeRequest) -> None:
        self.job_id = job_id
        self.request = request
        self.result: OptimizationResult | None = None
        self.messages: list[WsMessage] = []
        self.subscribers: set[asyncio.Queue[WsMessage]] = set()
        self.completed = asyncio.Event()


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}

    def create_job(self, request: OptimizeRequest) -> str:
        job_id = uuid4().hex[:8]
        self._jobs[job_id] = JobRecord(job_id, request)
        return job_id

    def get_result(self, job_id: str) -> OptimizationResult | None:
        record = self._jobs.get(job_id)
        return record.result if record else None

    async def subscribe(self, job_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        record = self._jobs.get(job_id)
        if record is None:
            await websocket.send_json(
                WsError(
                    job_id=job_id,
                    code="JOB_NOT_FOUND",
                    message="Job not found",
                    timestamp=datetime.now(UTC),
                ).model_dump(mode="json")
            )
            await websocket.close(code=1008)
            return

        queue: asyncio.Queue[WsMessage] = asyncio.Queue()
        record.subscribers.add(queue)
        try:
            for message in record.messages:
                await websocket.send_json(message.model_dump(mode="json"))
            if record.completed.is_set():
                await websocket.close()
                return
            while True:
                message = await queue.get()
                await websocket.send_json(message.model_dump(mode="json"))
                if message.type in {"done", "error"}:
                    await websocket.close()
                    return
        finally:
            record.subscribers.discard(queue)

    async def run_job(self, job_id: str) -> None:
        record = self._jobs[job_id]
        request = record.request
        created_at = datetime.now(UTC)
        record.result = OptimizationResult(
            job_id=job_id,
            transport_id=request.transport_id,
            status="running",
            created_at=created_at,
        )
        try:
            await self._publish_progress(
                record,
                "geocoding",
                10,
                "Geocoding customer addresses...",
            )
            transport = repository.get_transport(request.transport_id)
            if transport is None:
                await self._publish_error(record, "TRANSPORT_NOT_FOUND", "Transport not found")
                return

            await self._publish_progress(
                record,
                "distance_matrix",
                25,
                "Calculating road distances...",
            )
            if request.use_real_roads:
                source_stops = await enrich_stops_with_geocoding(transport.stops)
            else:
                source_stops = enrich_stops_from_local_coordinates(transport.stops)
            grouped_stops = group_stops_by_customer(source_stops)
            distance_source = "haversine"
            matrix = None
            if request.use_real_roads:
                matrix = await build_road_matrix(grouped_stops)
                if matrix is not None:
                    distance_source = "osrm-road-network"
            if matrix is None:
                matrix = build_distance_time_matrix(grouped_stops)

            await self._publish_progress(
                record,
                "vrp_solving",
                45,
                "Optimising delivery route...",
            )
            route_indices, solver_name = solve_route(
                grouped_stops,
                matrix,
                request.truck_type,
                request.respect_time_windows,
                request.solver_time_limit_s,
            )
            ordered_stops = apply_route(grouped_stops, route_indices)
            route = build_route_result(
                transport,
                request,
                ordered_stops,
                route_indices,
                matrix,
                solver_name,
                distance_source,
            )
            await self._publish(record, WsPartialResult(job_id=job_id, route=route, timestamp=datetime.now(UTC)))

            await self._publish_progress(
                record,
                "pallet_packing",
                65,
                "Planning truck load configuration...",
            )
            load = build_load_plan(transport, request, ordered_stops)
            if load.pallet_slots_used > load.pallet_slots_total:
                await self._publish_error(
                    record,
                    "PACKING_OVERFLOW",
                    f"Load needs {load.pallet_slots_used} pallet slots but truck only has {load.pallet_slots_total}",
                )
                return

            await self._publish_progress(
                record,
                "pick_list",
                80,
                "Generating warehouse pick list...",
            )
            await self._publish_progress(
                record,
                "visualization",
                90,
                "Building 3D visualization...",
            )
            route_geojson = None
            if request.use_real_roads:
                route_geojson = await build_route_geojson(grouped_stops, route_indices)
            viz = build_truck_visualization(load, ordered_stops, route_geojson)

            await self._publish_progress(
                record,
                "done",
                100,
                "Optimisation complete",
            )
            result = OptimizationResult(
                job_id=job_id,
                transport_id=transport.transport_id,
                status="done",
                created_at=created_at,
                completed_at=datetime.now(UTC),
                route=route,
                load=load,
                viz=viz,
            )
            record.result = result
            await self._publish(record, WsResult(job_id=job_id, result=result, timestamp=datetime.now(UTC)))
            await self._publish(record, WsDone(job_id=job_id, timestamp=datetime.now(UTC)))
        except Exception as exc:
            await self._publish_error(record, "OPTIMIZATION_ERROR", str(exc))

    async def _publish_progress(self, record: JobRecord, phase: str, pct: int, message: str) -> None:
        await self._publish(
            record,
            WsProgress(
                job_id=record.job_id,
                phase=phase,
                pct=pct,
                message=message,
                timestamp=datetime.now(UTC),
            ),
        )

    async def _publish_error(self, record: JobRecord, code: str, message: str) -> None:
        now = datetime.now(UTC)
        if record.result is None:
            record.result = OptimizationResult(
                job_id=record.job_id,
                transport_id=record.request.transport_id,
                status="error",
                created_at=now,
                completed_at=now,
                error_message=message,
            )
        else:
            record.result.status = "error"
            record.result.completed_at = now
            record.result.error_message = message
        await self._publish(
            record,
            WsError(
                job_id=record.job_id,
                code=code,
                message=message,
                timestamp=now,
            ),
        )

    async def _publish(self, record: JobRecord, message: WsMessage) -> None:
        record.messages.append(message)
        if message.type in {"done", "error"}:
            record.completed.set()
        for queue in list(record.subscribers):
            await queue.put(message)


job_manager = JobManager()
