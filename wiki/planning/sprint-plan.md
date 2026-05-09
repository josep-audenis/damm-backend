# 24h Hackathon Sprint Plan — Backend

## Schedule Overview

| Phase | Hours | Focus |
|-------|-------|-------|
| 0 — Setup | 0–1h | Repo, env, FastAPI skeleton |
| 1 — Data Layer | 1–4h | Parse Excel, geocode, domain models |
| 2 — Route Optimization | 4–8h | OR-Tools VRP or nearest neighbor |
| 3 — Load Optimization | 8–13h | Bin packing, returnable model |
| 4 — Integration | 13–17h | Combined endpoint, frontend sync |
| 5 — Gemini Agent | 17–20h | Optional: explanation/recommendation |
| 6 — Polish & Demo | 20–24h | Testing, demo data, pitch prep |

---

## Phase 0 — Setup (0–1h)

**Goal**: Running FastAPI server with health endpoint.

```bash
mkdir backend && cd backend
python -m venv venv && source venv/bin/activate
pip install fastapi uvicorn ortools geopy python-dotenv
```

```python
# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Damm Smart Truck API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
def health(): return {"status": "ok"}
```

```bash
uvicorn main:app --reload --port 8000
```

✅ Done when: `GET /health` returns 200.

**Coordinate with frontend team**: agree on base URL and CORS settings. Share the OpenAPI docs URL: `http://localhost:8000/docs`

---

## Phase 1 — Data Layer (1–4h)

**Goal**: Read `data/app_db.json`, expose `/data` endpoints, geocode addresses.

### Hour 1: DB repository
- [ ] Create `services/db_repository.py`
- [ ] Assemble transports, stops, products, and time windows from `data/app_db.json`
- [ ] Keep `DatabaseService.init_db()` responsible for schema normalization and migrations

### Hour 2: Domain models + data helpers
- [ ] `models/domain.py` — Stop, Product, Truck, TimeWindow, Pallet
- [ ] `models/schemas.py` — FastAPI request/response schemas
- [ ] Helper functions: `get_time_window()`, `get_case_dimensions()`, `is_returnable()`
- [ ] `build_transport(transport_id)` — assemble a full list of stops from the data

### Hour 3: Geocoding
- [ ] `services/geocoding.py` — geocode with geopy Nominatim
- [ ] Batch geocode DB customers that have missing coordinates
- [ ] Persist coordinates back to `data/app_db.json`

> **Tip**: Nominatim rate-limits to 1 req/s. For 1,368 addresses that's ~23 min. Start geocoding at the very beginning of this phase and let it run in the background while you write other code. Alternatively, use OpenRouteService's batch geocoding endpoint.

### Hour 4: Data endpoints + test
- [ ] `routers/data.py` — `/data/routes`, `/data/transport/{id}`, `/data/customers`
- [ ] Test with a known transport (e.g. 11420379 — JOSE VELEZ route in Mollet)
- [ ] Verify stop data looks correct (addresses, products, time windows)

✅ Done when: `GET /data/transport/11420379` returns full stop list with geocoded coords.

---

## Phase 2 — Route Optimization (4–8h)

**Goal**: `/optimize/route` endpoint returns a valid optimized stop order.

### Hour 5: Distance matrix
- [ ] `services/geocoding.py` — `haversine_matrix(stops)` function
- [ ] Test with 5 known Mollet stops, verify distances make sense
- [ ] If time allows: test OpenRouteService matrix API (needs API key)

### Hour 6: OR-Tools VRP
- [ ] `services/vrp_solver.py` — implement `solve_vrp(stops, truck, time_matrix)`
- [ ] Start with no time windows (just minimize distance)
- [ ] Add time window constraints
- [ ] Add capacity constraints (simple: pallet count per stop)
- [ ] Set 15-second solver time limit

### Hour 7: Fallback + endpoint
- [ ] Implement `nearest_neighbor_route()` as fallback
- [ ] Implement `two_opt_improve()` for quality improvement
- [ ] `routers/routes.py` — `POST /optimize/route` endpoint
- [ ] Return `RouteResult` with ordered stops + total distance/time

### Hour 8: Test & validate
- [ ] Run against transport 11420379 (Mollet, 8–10 stops, manageable)
- [ ] Compare optimized distance vs historical route
- [ ] Check time window violations
- [ ] Fix any obvious bugs

✅ Done when: `/optimize/route` with a real transport_id returns a plausible ordered route in < 5 seconds.

---

## Phase 3 — Load Optimization (8–13h)

**Goal**: `/optimize/load` takes an ordered stop list and returns pallet layout + pick list.

### Hour 9: Product classification + dimensions
- [ ] `services/bin_packing.py` — `classify_product(material_code, description)`
- [ ] Test classification on known SKUs (ED13 = bottle, CJ13 = crate, ED30 = barrel)
- [ ] `get_case_dimensions()` working correctly from ZM040

### Hour 10: Pallet packing
- [ ] `pack_products_to_pallets(stops_in_order, truck)` — layer-based stacking
- [ ] Respect stacking rules (barrels at bottom, cans on top)
- [ ] Handle overflow (stop requiring > 1 pallet)
- [ ] Returnable pallet reservation at rear

### Hour 11: Pick path + visualization data
- [ ] `generate_pick_list(pallets)` — sorted by warehouse location
- [ ] Build `visualization_data` dict for frontend 3D rendering
- [ ] `routers/loading.py` — `POST /optimize/load` endpoint

### Hour 12: Returnable logistics
- [ ] `estimate_returnables(stop)` — predict pickup quantities
- [ ] Dynamic capacity model (capacity changes as route progresses)
- [ ] Add returnables to visualization data (show growing pile in rear)

### Hour 13: Test load optimization
- [ ] Test on transport 11420379
- [ ] Verify pallet count ≤ truck capacity
- [ ] Verify pick list has correct location codes
- [ ] Manually sanity-check one stop's pallet

✅ Done when: `/optimize/load` returns sensible pallets + pick list for a real transport.

---

## Phase 4 — Integration (13–17h)

**Goal**: Single `/optimize/full` endpoint works end-to-end. Frontend can demo it.

### Hour 14: Combined endpoint
- [ ] `POST /optimize/full` — calls route optimizer then load optimizer
- [ ] Wire `routers/routes.py` into main.py
- [ ] Wire `routers/loading.py` into main.py
- [ ] Wire `routers/data.py` into main.py

### Hour 15: Frontend sync
- [ ] Share API docs with frontend team (`/docs`)
- [ ] Walk through the `/optimize/full` response shape
- [ ] Agree on `visualization_data` format for 3D truck view
- [ ] Fix any schema mismatches

### Hour 16: Error handling + edge cases
- [ ] Handle missing time windows gracefully
- [ ] Handle missing dimensions (use defaults)
- [ ] Handle geocoding failures (use postal-code centroid)
- [ ] Add proper HTTP error responses (422, 500)

### Hour 17: Prepare demo transport
- [ ] Pick 2–3 "demo-ready" transports from the data (manageable size, interesting area)
- [ ] Verify these work end-to-end
- [ ] Write brief summary of optimization gains for each

**Good demo transports to try:**
| Transport | Route | Driver | Stops | Why interesting |
|-----------|-------|--------|-------|-----------------|
| 11420379 | DR0006 | JOSE VELEZ | ~8 stops in Mollet | Tight urban area, many returnables |
| 11420393 | DR0051 | PEREZ NEWMAN | ~11 stops in Vic | Spread across a city, multiple time windows |
| 11420330 | DR0040 | CRISTIAN LORENTE | ~5 stops in Granollers | Mix of restaurants, mid-sized |

✅ Done when: Frontend can render a full optimized route + truck load for at least one transport.

---

## Phase 5 — Gemini Agent (17–20h) [OPTIONAL]

**Goal**: Add AI-generated explanations to route and load results.

Only start this if Phase 4 is fully complete and stable.

### Hour 18: Setup Gemini
- [ ] `pip install google-generativeai`
- [ ] Add `GEMINI_API_KEY` to `.env`
- [ ] `services/gemini_agent.py` — `explain_route()` and `explain_load()` functions
- [ ] Test prompt engineering on one example

### Hour 19: Explanation endpoint
- [ ] `routers/agents.py` — `POST /agent/explain`
- [ ] Wire explanation call into `/optimize/full` response (add `explanation` field)
- [ ] Add `POST /agent/suggest` for improvement recommendations

### Hour 20: Recommendation agent
- [ ] Prompt to suggest operational improvements (e.g., merge zones, reorder warehouse)
- [ ] Test with a real transport

✅ Done when: `/optimize/full` response includes a human-readable explanation of key routing/loading decisions.

---

## Phase 6 — Polish & Demo Prep (20–24h)

**Goal**: Everything works, looks good, ready to pitch.

### Hour 21–22: Bug fixes & stability
- [ ] Run end-to-end test on all 3 demo transports
- [ ] Fix any crashes or wrong outputs
- [ ] Add logging to show solver decisions
- [ ] Measure & document optimization gains (distance saved %, time window compliance)

### Hour 23: Demo data & pitch prep
- [ ] Prepare a "canned demo" — hardcode the best demo transport to always load first
- [ ] Document the 3 key metrics for the pitch:
  - Distance reduction % vs historical route
  - Time window violations: before vs after
  - Pick time estimate: reference loading vs optimized loading
- [ ] Write a 1-page summary of the technical approach for judges

### Hour 24: Final testing
- [ ] Fresh environment test (install from requirements.txt, run)
- [ ] Backend + frontend integration final check
- [ ] Pitch rehearsal — demo the full flow

---

## MVP Definition

The minimum to show judges something impressive:

1. ✅ Parse real DDI data (use Hackaton.xlsx + Horarios Entrega.XLSX)
2. ✅ Optimize a real route (at least nearest neighbor)
3. ✅ Show a load plan (even simplified pallet assignment)
4. ✅ Compare to historical route (show improvement numbers)
5. ✅ Visualize the result (even a simple map in the frontend)

Everything else (Gemini, full 3D bin-packing, warehouse layout recommendation) is a bonus.

---

## Scope Risk Management

| Risk | Mitigation |
|------|-----------|
| OR-Tools too complex to set up quickly | Have nearest neighbor ready as Day 1 fallback |
| Geocoding takes too long | Use postal code centroids as fallback; precompute at setup |
| Frontend integration delays | Expose `/docs` early; agree on schemas in Hour 15 |
| 3D bin-packing too complex | Use layer-based 2D stacking instead |
| Gemini API quota | Use Haiku/Flash model; cache responses for identical inputs |
| Data quality issues in Excel | Add defensive parsing (try/except, fillna defaults) everywhere |

---

## Quick Reference: Useful Test Commands

```bash
# Start the server
uvicorn main:app --reload --port 8000

# Test health
curl http://localhost:8000/health

# Get a specific transport
curl http://localhost:8000/api/v1/data/transport/11420379

# Optimize a route
curl -X POST http://localhost:8000/api/v1/optimize/full \
  -H "Content-Type: application/json" \
  -d '{"transport_id": "11420379", "truck_type": "6pal"}'

# API docs (browser)
open http://localhost:8000/docs
```
