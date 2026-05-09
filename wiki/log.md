# SmartTruck Wiki Log

## [2026-05-09] update | Strict CSV order import (no auto-create)

Reverted the JSON DB to the pre-import baseline (200 customers / 773 materials / 12,194 orders) and removed the `create_missing_materials` / `create_missing_customers` form fields from `POST /api/v1/data/orders/import`. The importer now skips rows whose customer or material is unknown and reports them via `unknown_customers` and `unknown_materials`. Updated the static demo, tests, README, and `api-contract.md`. Added a curated `data/sample_orders.csv` whose customers and materials all exist in the seeded DB.

## [2026-05-09] update | CSV order import endpoint and demo UI button

Added `POST /api/v1/data/orders/import` (multipart) backed by `services/order_import.py`. The importer parses `;`/`,` CSVs, matches customers by uppercase name and materials by uppercase description, auto-creates missing materials by default, and skips unknown customers unless explicitly enabled. Added `python-multipart` dependency, exposed `load`/`save`/`stage_insert` helpers on `db_service`, wired an Import CSV form into the static demo, and updated `api-contract.md` and `architecture.md`.

## [2026-05-09] query | Project context and implementation overview

Reviewed the wiki contracts and backend implementation to summarize the Damm Smart Truck project, including FastAPI routing, JSON database storage, domain assembly, optimization flow, WebSocket jobs, static demo UI, and test coverage.

## [2026-05-09] update | Add order delivery flag and exact geocoding

Added `orders.delivered_flag` with default `false` for existing and bootstrapped orders. Recomputed coordinates for the 200-customer demo database using exact address queries only, with fallback geocoding disabled; 83 customers and 619 related delivery stops now have coordinates.

## [2026-05-09] update | Reduce checked-in DB for demo

Reduced `data/app_db.json` to 200 randomly selected customers with complete address fields and no `S/N` addresses. Removed related rows for excluded customers and pruned dependent orders, delivery stops, delivery lines, transports, materials, dimensions, routes, and drivers to maintain referential integrity.

## [2026-05-09] update | Simplified JSON database schema

Removed stored source identifiers and unused reservation fields from catalog tables: customer time windows no longer store `shift` or `is_closed`; customers, drivers, material types, materials, warehouses, delivery stops, and transports now rely on integer `id` for stored identity; manufacturer metadata, warehouse locations, and source document tables were removed; trucks now store only `id`, `plate`, `capacity_pallets`, and `warehouse_id`; order quantities moved from `delivery_lines` into the new `orders` table.

## [2026-05-09] ingest | Database schema documented

Created `wiki/data/db-schema.md` from `services/database.py`. Documents all 13 tables (fields, types, FK relationships, natural keys, bootstrap row counts) and the ER diagram. Updated `wiki/index.md` with the new page.


## [2026-05-09] update | Real data preprocessing contract

Accepted the real data unit contract update for `TB`, `EST`, `PQ`, `TIR`, `BID`, and `ZPR`. Added `RouteSummary` to the data model contract for `GET /api/v1/data/routes`.
## [2026-05-09] ingest | Integrate capital-letter root docs into wiki

Processed and integrated five root-level markdown files into the wiki structure:

- `ALGORITHMS.md` → `wiki/technical/algorithms.md` (route CVRPTW, bin-packing, warehouse pick optimization)
- `BACKEND_PLAN.md` → `wiki/technical/architecture.md` (tech stack, API design, data pipeline, phases)
- `DATA_MODELS.md` → Enhanced `wiki/contracts/data-models.md` with comprehensive Pydantic schemas
- `DATA_SCHEMA.md` → removed after the app moved to the DB-only runtime schema
- `SPRINT_PLAN.md` → `wiki/planning/sprint-plan.md` (24h timeline, risk mitigation, MVP definition)

Updated `wiki/index.md` with new sections: Technical, Data, Planning.

## [2026-05-09] lint | Wiki index reconciliation

Removed stale root-level entries (`DATA_SCHEMA.md`, `DATA_MODELS.md`, `ALGORITHMS.md`, `BACKEND_PLAN.md`, `SPRINT_PLAN.md` — all deleted). Updated `index.md` and `CLAUDE.md` wiki table to reflect actual `wiki/` structure.

## [2026-05-09] setup | Shared LLM Wiki Snapshot

Created the shared SmartTruck wiki from the definitive plan, Karpathy LLM-wiki workflow, and `DATA_MODELS.md`.

Key decisions:

- Use shared markdown contracts because frontend and backend repos will be developed separately.
- Treat data models, API paths, enum values, and WebSocket messages as the most important coordination contract.
- Use `/api/v1/optimize/full` plus `/ws/jobs/{job_id}` as the primary optimization workflow.
- Keep backend deterministic; use OpenAI Agents SDK only for explanations and generated operational summaries.
