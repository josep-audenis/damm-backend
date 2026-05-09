# Separation Of Concerns

Frontend and backend will be developed separately. This page defines ownership boundaries.

## Shared Contract Owns

The shared wiki contract owns:

- Endpoint paths.
- Request and response schemas.
- WebSocket message schema.
- Progress phase keys.
- Enum values.
- Domain vocabulary.
- Visualization payload shape.

Neither repo should silently change these.

## Backend Owns

The backend owns:

- Reading Excel files.
- Normalizing Damm/DDI operational data.
- Geocoding and distance matrix building.
- Route optimization.
- Load planning.
- Returnables modeling.
- Warehouse pick list generation.
- Strategy scoring.
- Job lifecycle.
- WebSocket progress messages.
- Export payload generation.
- Optional OpenAI Agents SDK explanations.

The backend does **not** own:

- React component layout.
- mapcn rendering details.
- Client-side state management.
- Visual styling.

## Frontend Owns

The frontend owns:

- Next.js routing.
- User workflow.
- Map rendering.
- Truck visualization rendering.
- Progress UI.
- KPI panels.
- Strategy comparison UI.
- Export presentation.
- Error and empty states.
- Local mock data that conforms to the contract.

The frontend does **not** own:

- Route optimization.
- Load optimization.
- Scoring truth.
- Returnables calculations.
- Data normalization.

## Shared Development Rule

If a developer needs a field that is not in the contract:

1. Add a local code TODO or mock adapter.
2. Propose the field in `wiki/decisions/`.
3. Add a log entry.
4. Do not assume the other repo already has it.

## Naming Rule

Backend transport payloads use the Pydantic model names from the contract. JSON field names should stay stable. Prefer snake_case for backend schema compatibility unless both repos explicitly agree to camelCase.

Frontend may map snake_case to camelCase internally, but the API client layer must preserve the backend contract.

