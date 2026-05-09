# Frontend Agent Instructions

Read these before modifying the frontend repo.

## Required Context

Read in order:

1. `wiki/index.md`
2. `wiki/contracts/data-models.md`
3. `wiki/contracts/api-contract.md`
4. `wiki/contracts/separation-of-concerns.md`

## Frontend Mission

Build the SmartTruck planner UI:

- Select a transport.
- Start optimization.
- Open WebSocket progress.
- Render partial route as soon as available.
- Render final route, truck visualization, pick list, KPIs, and explanations.
- Provide export/pitch views.

## Contract Rules

- Use the contract models exactly at the API boundary.
- Do not invent backend fields.
- If using mock data, it must validate against the shared schemas.
- Accept snake_case fields from backend unless a generated client maps them.
- Recognize exact WebSocket message types: `progress`, `partial`, `result`, `done`, `error`.
- Recognize exact progress phase keys from `api-contract.md`.

## Implementation Order

1. App shell.
2. Zod schemas or generated OpenAPI client.
3. Transport selector.
4. Optimize button.
5. WebSocket job hook.
6. Progress UI.
7. Route map.
8. Truck visualization.
9. Pick list panel.
10. KPI panel.
11. Explanations.
12. Export views.

## Main UX Flow

```txt
Select transport
  -> POST /api/v1/optimize/full
  -> connect WS /ws/jobs/{job_id}
  -> show progress
  -> render WsPartialResult route
  -> render WsResult route/load/viz/pick list
  -> close on WsDone
```

## Visualization Rules

Map:

- Use mapcn + MapLibre.
- Show depot, numbered stops, route line, selected stop state.
- Render `route_geojson` if available.

Truck:

- Use `TruckVisualization`.
- Interpret coordinates in centimeters.
- Do not ask backend for rendering-specific CSS.
- The backend gives geometry; frontend owns visuals.

## UI Rules

- This is an operations app, not a marketing site.
- First screen should help the user start planning.
- Use compact, readable panels.
- Keep truck slots dimensionally stable.
- Make progress and errors obvious.
- Do not hide warnings.

## Logging Wiki Changes

If you need a contract change:

1. Update local `wiki/contracts/*` only as a proposal.
2. Add a line to `wiki/log.md`.
3. Add a decision page in `wiki/decisions/`.
4. Mention the contract change in your final response or PR notes.

