# Damm Smart Truck — Schema & Wiki

## Wiki Structure

This repo uses an LLM-maintained wiki pattern. Three layers:

- **Raw sources** — `data/raw/` Excel files. Immutable. Never modify.
- **Wiki** — LLM-generated `.md` files in repo root. LLM owns and maintains these.
- **Schema** — this file (CLAUDE.md). Defines conventions and workflows.

### Wiki pages

| File | Category | Purpose |
|------|----------|---------|
| [index.md](index.md) | Meta | Root index (pointer to wiki/) |
| [wiki/index.md](wiki/index.md) | Meta | Canonical wiki catalog |
| [wiki/log.md](wiki/log.md) | Meta | Append-only activity log |
| [README.md](README.md) | Overview | Project overview |
| [wiki/contracts/data-models.md](wiki/contracts/data-models.md) | Contracts | Domain, request/response, WebSocket schemas |
| [wiki/contracts/api-contract.md](wiki/contracts/api-contract.md) | Contracts | Endpoint paths and payload shapes |
| [wiki/contracts/separation-of-concerns.md](wiki/contracts/separation-of-concerns.md) | Contracts | Frontend/backend ownership boundaries |
| [wiki/backend/agent-instructions.md](wiki/backend/agent-instructions.md) | Technical | Backend implementation rules |
| [wiki/frontend/agent-instructions.md](wiki/frontend/agent-instructions.md) | Technical | Frontend implementation rules |
| [wiki/decisions/README.md](wiki/decisions/README.md) | Planning | Architectural decisions |

### Conventions

- Every wiki page has a `# Title` and optional YAML frontmatter (`tags`, `sources`, `updated`).
- Cross-references use markdown links: `[page](page.md)`.
- On ingest: read source → discuss key takeaways → write/update summary page → update index.md → update related entity/concept pages → append to log.md.
- On query: read index.md → drill into relevant pages → synthesize answer → optionally file answer as new wiki page.
- On lint: check for contradictions, stale claims, orphan pages, missing cross-references.

### Log format

Each log entry: `## [YYYY-MM-DD] <type> | <title>`  
Types: `ingest`, `query`, `lint`, `update`

---

# Damm Smart Truck — Backend Context

## Project Summary

**Hackathon:** Interhack Barcelona 2026 (24h)  
**Challenge sponsor:** Damm / DDI (Distribució Directa Integral)  
**Goal:** Jointly optimize delivery route + truck load configuration for DDI's daily distribution operations.

DDI distributes beverages and food items across Catalonia (primarily Vallès Oriental / Mollet area). Each truck does 15–25 stops per day. Currently, drivers decide their own route and the warehouse loads products grouped by SKU reference, not by delivery order. This causes inefficiency: drivers hunt for products mid-route, the load order doesn't match delivery order, and returnable logistics (≈60% of products are returnable bottles/crates) is handled ad hoc.

---

## Repo Structure (Backend)

```
backend/
├── main.py                 # FastAPI app entry point
├── routers/
│   ├── routes.py           # Route optimization endpoints
│   ├── loading.py          # Truck load optimization endpoints
│   ├── data.py             # Data ingestion / preview endpoints
│   └── agents.py           # Gemini agent endpoints (optional)
├── services/
│   ├── vrp_solver.py       # Vehicle Routing Problem logic
│   ├── bin_packing.py      # 3D bin-packing / load config logic
│   ├── data_loader.py      # Excel parsing + caching
│   ├── geocoding.py        # Address → lat/lng
│   └── gemini_agent.py     # Google Gemini integration (optional)
├── models/
│   ├── schemas.py          # Pydantic request/response models
│   └── domain.py           # Core domain types (Stop, Product, Truck, etc.)
├── data/
│   ├── raw/                # Original Excel files (gitignored if large)
│   └── processed/          # Cached/parsed versions (JSON/parquet)
├── tests/
│   └── ...
├── requirements.txt
└── .env.example
```

---

## Key Data Files

| File | Description | Rows |
|------|-------------|------|
| `Hackaton.xlsx` → *Detalle entrega* | 2 months of delivery lines | 82,849 |
| `Hackaton.xlsx` → *Cabecera Transporte* | Transport headers (one per truck day) | 8,927 |
| `Hackaton.xlsx` → *Direcciones* | Customer addresses | 1,368 |
| `Hackaton.xlsx` → *ZONAS* | Zone → Route → Driver mapping | 1,203 |
| `Hackaton.xlsx` → *Materiales zubic* | Product → warehouse location | 1,489 |
| `Horarios Entrega.XLSX` | Customer delivery time windows | 1,015 |
| `Layout Mollet.xlsx` | DDI Mollet warehouse floor plan grid | — |
| `ZM040.XLSX` | Product dimensions & weights (all SKUs) | 48,457 |

---

## Domain Vocabulary

| Term | Meaning |
|------|---------|
| **DR** | Ruta de Repartidor — the route assignment unit (driver + route + zones + customers) |
| **Transporte** | One truck's full day: a single transport number with all its delivery stops |
| **Entrega** | An individual delivery (one stop at one customer) |
| **Ruta** | Route code, e.g. `DR0001`, `DR0006`. Each maps to a set of zones and customers |
| **Zona (DD..)** | Sub-zone within a route, groups nearby customers |
| **Destinatario mcía.** | Customer ID (numeric) |
| **Material** | SKU code, e.g. `ED13` = Estrella Damm 1/3 RET (returnable bottle) |
| **RET** | Returnable product — bottle/crate to be picked back up from customer |
| **CJ13** | Empty crate — specifically tracked as a returnable |
| **Palets** | Pallets. Trucks hold 6 or 8 pallets (van = 3 pallets) |
| **Turno** | Delivery shift: 1 = morning, 2 = afternoon |
| **Ubic.** | Warehouse location code for a product (e.g. `FA05A2`, `CB06A2`) |

---

## Fleet

| Type | Count | Pallet Capacity |
|------|-------|-----------------|
| Truck (6-pallet) | 11 | 6 pallets |
| Truck (8-pallet) | 4 | 8 pallets |
| Van | 1 | 3 pallets |

Trucks have **side tarpaulin access** (lona lateral) — pallets can be accessed from the side, not just the back. This is critical for load order: products for later stops can be placed deeper or higher, as long as the pallet for the next stop is accessible from the side.

---

## Evaluation Criteria (Hackathon judges)

| Criterion | Weight |
|-----------|--------|
| Real applicability to Damm context | 30% |
| Technical quality | 25% |
| Potential impact | 20% |
| Creativity & originality | 15% |
| Communication / pitch | 10% |

**Implication:** Focus on real applicability first (use their actual data), then technical quality. A working demo beats a theoretically perfect model that doesn't run.

---

## Critical Constraints

1. **Time windows are hard constraints** — some customers have 15-minute windows (e.g. PIZZA VALLES: 09:00–09:15). Route must respect these.
2. **Returnable logistics** — ~60% of products are returnable. The truck must have space for returnables being picked up at each stop, which reduces usable load capacity dynamically.
3. **Side access** — load order matters differently than a rear-access-only truck. Products for early stops should be on a pallet accessible from the side without unloading later-stop products.
4. **Warehouse location** — load order should respect warehouse pick path (pick all items from aisle FA before going to CB, etc.) to minimize pick time.
5. **Product stacking rules** — barrels can't be stacked on soft cases. Latas/cans can be stacked high. Retornables have defined pallet heights.
