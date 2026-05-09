# SmartTruck Wiki Log

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

## [2026-05-09] lint | Wiki index reconciliation

Removed stale root-level entries (`DATA_SCHEMA.md`, `DATA_MODELS.md`, `ALGORITHMS.md`, `BACKEND_PLAN.md`, `SPRINT_PLAN.md` — all deleted). Updated `index.md` and `CLAUDE.md` wiki table to reflect actual `wiki/` structure.

## [2026-05-09] setup | Shared LLM Wiki Snapshot

Created the shared SmartTruck wiki from the definitive plan, Karpathy LLM-wiki workflow, and `DATA_MODELS.md`.

Key decisions:

- Use shared markdown contracts because frontend and backend repos will be developed separately.
- Treat data models, API paths, enum values, and WebSocket messages as the most important coordination contract.
- Use `/api/v1/optimize/full` plus `/ws/jobs/{job_id}` as the primary optimization workflow.
- Keep backend deterministic; use OpenAI Agents SDK only for explanations and generated operational summaries.
