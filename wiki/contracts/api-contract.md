# API Contract

This page is the shared frontend/backend communication contract.

## Base URL

```txt
http://localhost:8000
```

API base path:

```txt
/api/v1
```

## Main Flow

```txt
Frontend
  POST /api/v1/optimize/full
Backend
  returns { job_id, status, ws_url }
Frontend
  opens WebSocket /ws/jobs/{job_id}
Backend
  emits progress, partial route, final result, done/error
Frontend
  renders map, truck, pick list, KPIs, explanations
```

## Required Endpoints

### Health

```txt
GET /api/v1/health
```

Response model:

```txt
HealthResponse
```

### List Routes / Transports

```txt
GET /api/v1/data/routes
GET /api/v1/data/transports
GET /api/v1/data/transport/{transport_id}
GET /api/v1/data/customers/{customer_id}
```

Primary list item:

```txt
TransportSummary
```

### Import Orders From CSV

```txt
POST /api/v1/data/orders/import   (multipart/form-data)
```

Form fields:

| Field | Type | Notes |
|---|---|---|
| `file` | file | CSV with header row. Required columns: `customer_name`, `qty`, `unit`. Optional columns: `material_code`, `material_name`, `due_date`, `quantity`, `sales_unit`. Delimiter `;` or `,`. |
| `due_date` | date | Default `today`. Used when a row has no `due_date` column. |

The importer is strict: rows are inserted only when both the customer (matched by uppercase `name`) and the material (matched by uppercase `description`, falling back to `material_code`) already exist in the database. Unknown customers and materials are skipped — they are never created. A sample CSV that resolves against the seeded demo DB lives at `data/sample_orders.csv`.

Response model:

```txt
OrderImportResponse {
  status: "ok",
  received: int,
  inserted: int,
  skipped: int,
  unknown_customers: list[str],
  unknown_materials: list[str],
  errors: list[{ row: int, reason: str, raw: dict }],
}
```

Skip reasons: `missing_required_fields`, `invalid_quantity`, `non_positive_quantity`, `unknown_customer`, `unknown_material`. The first 200 row errors are returned.

### Start Full Optimization

```txt
POST /api/v1/optimize/full
```

Request model:

```txt
OptimizeRequest
```

Response:

```json
{
  "job_id": "a3f2b1c8",
  "status": "pending",
  "ws_url": "/ws/jobs/a3f2b1c8"
}
```

### WebSocket Job Updates

```txt
WS /ws/jobs/{job_id}
```

Messages:

```txt
WsProgress
WsPartialResult
WsResult
WsDone
WsError
```

### Optional Result Fetch

Useful if the frontend refreshes after a job completes.

```txt
GET /api/v1/jobs/{job_id}
```

Response:

```txt
OptimizationResult
```

### Optional Exports

```txt
GET /api/v1/jobs/{job_id}/export/driver
GET /api/v1/jobs/{job_id}/export/warehouse
GET /api/v1/jobs/{job_id}/export/pitch
```

These should be JSON first. PDF/Excel export can be added later.

## Progress Phases

The backend emits these exact phase keys:

| Phase key | pct | Message |
|---|---:|---|
| `geocoding` | 10 | Geocoding customer addresses... |
| `distance_matrix` | 25 | Calculating road distances... |
| `vrp_solving` | 45 | Optimising delivery route... |
| `pallet_packing` | 65 | Planning truck load configuration... |
| `pick_list` | 80 | Generating warehouse pick list... |
| `visualization` | 90 | Building 3D visualization... |
| `explanation` | 95 | Generating AI explanation... |
| `done` | 100 | Optimisation complete |

The frontend may render friendlier labels, but must recognize these keys.

## Error Codes

| Code | Meaning | Frontend behavior |
|---|---|---|
| `JOB_NOT_FOUND` | WebSocket connected to unknown job | Show session expired |
| `TRANSPORT_NOT_FOUND` | Transport not in dataset | Show validation error |
| `GEOCODING_FAILED` | Geocoding failed | Show warning and allow fallback |
| `NO_FEASIBLE_ROUTE` | Solver found no route | Show reduce constraints hint |
| `PACKING_OVERFLOW` | Load exceeds truck capacity | Show capacity alert |
| `SOLVER_TIMEOUT` | Solver timed out | Show best result if available |
| `AGENT_ERROR` | OpenAI explanation unavailable | Continue without explanation |

## Contract Rule

The frontend should treat `WsResult.result` as the source of truth for final rendering.

The backend should try to emit `WsPartialResult` after route optimization so the frontend can render the map before pallet packing finishes.

