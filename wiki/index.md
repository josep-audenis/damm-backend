# SmartTruck Wiki Index

## Contracts

- [Data Models](contracts/data-models.md): canonical domain, request/response, visualization, and WebSocket schemas.
- [API Contract](contracts/api-contract.md): endpoint paths, payload shapes, and frontend/backend communication flow.
- [Separation Of Concerns](contracts/separation-of-concerns.md): what backend owns, what frontend owns, and what must remain shared.

## Technical

- [Algorithms](technical/algorithms.md): route optimization (CVRPTW), bin-packing, warehouse picking logic.
- [Architecture](technical/architecture.md): tech stack, API design, DB-backed API flow, implementation priorities.

## Data

- [DB Schema](data/db-schema.md): app_db.json table definitions, fields, types, FK relationships, and row counts.

## Planning

- [Sprint Plan](planning/sprint-plan.md): 24h hackathon timeline, phases, MVP definition, risk mitigation.

## Backend

- [Backend Agent Instructions](backend/agent-instructions.md): backend repo implementation rules.

## Frontend

- [Frontend Agent Instructions](frontend/agent-instructions.md): frontend repo implementation rules.

## Decisions

- [Decision Log](decisions/README.md): architectural decisions and contract proposals.
- [Preserve Real Delivery Units](decisions/2026-05-09-real-data-units.md): accepted contract change for source delivery units found during Excel preprocessing.
- [Simplified JSON Database Schema](decisions/2026-05-09-simplified-json-db-schema.md): accepted change removing stored source identifiers, dropping warehouse locations, and moving ordered quantities into `orders`.

## Log

- [log.md](log.md): chronological wiki maintenance log.
