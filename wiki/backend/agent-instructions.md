# Backend Agent Instructions

Read these before modifying the backend repo.

## Required Context

Read in order:

1. `wiki/index.md`
2. `wiki/contracts/data-models.md`
3. `wiki/contracts/api-contract.md`
4. `wiki/contracts/separation-of-concerns.md`

## Backend Mission

Build the deterministic SmartTruck backend:

- Load real Damm/DDI data.
- Normalize into the shared models.
- Run route optimization.
- Run truck load planning.
- Generate warehouse pick list.
- Emit WebSocket progress.
- Return `OptimizationResult`.
- Optionally generate explanations using OpenAI Agents SDK.

## Contract Rules

- Implement Pydantic models from `wiki/contracts/data-models.md`.
- Use `/api/v1/optimize/full` as the main optimization endpoint.
- Use `/ws/jobs/{job_id}` for progress updates.
- Emit exact WebSocket `type` values: `progress`, `partial`, `result`, `done`, `error`.
- Emit exact progress phase keys from `api-contract.md`.
- Do not rename fields without a contract proposal.

## Implementation Order

1. Pydantic enums and models.
2. Health endpoint.
3. Data loader.
4. Transport summary/detail endpoints.
5. Job manager and WebSocket endpoint.
6. Fallback route solver.
7. OR-Tools route solver.
8. Pallet/load planner.
9. Pick list generator.
10. Visualization payload builder.
11. Export endpoints.
12. Optional OpenAI explanation service.

## Optimization Rules

Route:

- Start with haversine matrix and nearest neighbor + 2-opt.
- Add OR-Tools once fallback works.
- Time windows should be respected when clean; ambiguous missing data should degrade gracefully.

Load:

- Use pallet/layer model, not full 3D bin packing.
- Use product categories from the shared enum.
- Reserve returnable pallet capacity when `include_returnables` is true.
- Generate `LoadPlan.pick_list`.

## Agent Explanation Rules

OpenAI Agents SDK may be used only after deterministic route/load results exist.

Agent output must reference computed facts:

- route distance
- time windows
- pallet utilization
- returnable risk
- pick list
- warnings

Never let the agent invent stops, products, route metrics, or load assignments.

## Logging Wiki Changes

If you change the backend contract:

1. Update local `wiki/contracts/*`.
2. Add a line to `wiki/log.md`.
3. Add a decision page in `wiki/decisions/`.
4. Mention the contract change in your final response or PR notes.

