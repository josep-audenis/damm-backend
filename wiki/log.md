# SmartTruck Wiki Log

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
- `DATA_SCHEMA.md` → `wiki/data/schema.md` (field glossary, data relationships, sample queries)
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
