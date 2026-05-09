# SmartTruck Wiki Log

## [2026-05-09] lint | Wiki index reconciliation

Removed stale root-level entries (`DATA_SCHEMA.md`, `DATA_MODELS.md`, `ALGORITHMS.md`, `BACKEND_PLAN.md`, `SPRINT_PLAN.md` — all deleted). Updated `index.md` and `CLAUDE.md` wiki table to reflect actual `wiki/` structure.

## [2026-05-09] setup | Shared LLM Wiki Snapshot

Created the shared SmartTruck wiki from the definitive plan, Karpathy LLM-wiki workflow, and `DATA_MODELS.md`.

Key decisions:

- Use shared markdown contracts because frontend and backend repos will be developed separately.
- Treat data models, API paths, enum values, and WebSocket messages as the most important coordination contract.
- Use `/api/v1/optimize/full` plus `/ws/jobs/{job_id}` as the primary optimization workflow.
- Keep backend deterministic; use OpenAI Agents SDK only for explanations and generated operational summaries.

