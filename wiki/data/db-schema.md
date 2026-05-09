# Database Schema (app_db.json)

---
tags: [database, schema, json-db]
sources: [services/database.py]
updated: 2026-05-09
---

The backend uses a JSON flat-file database at `data/app_db.json`. Structure:

```json
{
  "meta": { "generated_at": "<ISO timestamp>" },
  "seq":  { "<table>": <last_id_int>, ... },
  "tables": { "<table>": [ <row>, ... ], ... }
}
```

All rows have an auto-incremented integer `id` as primary key. Foreign keys are integer `id` references (not natural keys).

---

## Tables

### `warehouses`

One row per physical warehouse/depot.

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | PK |
| `code` | str | Natural key, e.g. `D131` |
| `name` | str | e.g. `DDI Mollet` |
| `storage_center_code` | str | SAP storage center code |
| `address` | str\|null | Street address |
| `postal_code` | str\|null | |
| `city` | str\|null | e.g. `Mollet del Vallès` |
| `lat` | float\|null | Geocoded latitude |
| `lng` | float\|null | Geocoded longitude |
| `created_at` | str | ISO timestamp |

Seeded on init: one row for `D131` (DDI Mollet).

---

### `warehouse_locations`

One row per physical shelf/slot within a warehouse. Sourced from *Materiales zubic* sheet.

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | PK |
| `warehouse_id` | int | FK → warehouses.id |
| `code` | str | Location code, e.g. `FA05A2` (natural key) |
| `storage_center_code` | str\|null | SAP `Ce.` field |
| `warehouse_section` | str\|null | `Alm.1` / `Alm.5` etc. |
| `base_unit` | str\|null | `CAJ` / `PAL` / `UN` |
| `manufacturer` | str\|null | |
| `manufacturer_code` | str\|null | |
| `lat` | float\|null | |
| `lng` | float\|null | |

Location code format: `FA05A2` → aisle `F`, sub-aisle `A`, bay `05`, column `A`, level `2`.

---

### `material_types`

Lookup table — product categories. Seeded on init, not imported from Excel.

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | PK |
| `code` | str | Natural key, e.g. `beer_bottle` |
| `name` | str | Display name |
| `description` | str | |

Seeded codes: `beer_bottle`, `beer_barrel`, `water`, `soft_drink`, `dairy`, `coffee`, `wine_spirits`, `food`, `disposable`, `gas`, `returnable_empty`.

---

### `materials`

One row per SKU. Sourced from *Detalle entrega* + *Materiales zubic* + *ZM040*.

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | PK |
| `code` | str | SKU code natural key, e.g. `ED13` |
| `description` | str | Product name |
| `base_unit` | str\|null | `CAJ` / `PAL` / `UN` |
| `material_type_id` | int\|null | FK → material_types.id |
| `manufacturer` | str\|null | |
| `manufacturer_code` | str\|null | |
| `product_hierarchy_code` | str\|null | SAP hierarchy, e.g. `00CF30ZZPCA1E4` |
| `is_returnable` | bool | True if bottle/crate must be returned |

Returnability rule: codes starting with `ED`, `VO`, `FD`, `DL`, `CJ`, or description contains `RET`.

---

### `material_dimensions`

Physical dimensions per packaging unit. Multiple rows per material (one per unit type). Sourced from *ZM040*.

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | PK |
| `material_id` | int | FK → materials.id |
| `unit` | str | `CAJ` / `PAL` / `UN` / `BOT` etc. |
| `counter` | int\|null | Units per packaging |
| `length_cm` | float\|null | Normalized to cm |
| `width_cm` | float\|null | Normalized to cm |
| `height_cm` | float\|null | Normalized to cm |
| `volume_l` | float\|null | Litres |
| `weight_gross_kg` | float\|null | Normalized to kg |
| `weight_net_kg` | float\|null | Normalized to kg |

Unit normalization: source may be MM or M → converted to cm; G/GR → converted to kg.

---

### `customers`

One row per customer. Sourced from *Direcciones* + *ZONAS*.

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | PK |
| `code` | str | Customer ID natural key, e.g. `91123456` |
| `name` | str\|null | Primary name (`Nombre 1`) |
| `name_2` | str\|null | Secondary name (`Nombre 2`) |
| `address` | str\|null | Street (`Calle`) |
| `postal_code` | str\|null | `CP` |
| `city` | str\|null | `Población` |
| `zone_code` | str\|null | Zone code, e.g. `DD13100002` |
| `zone_name` | str\|null | Zone name, e.g. `MOLLET PLANA LLADO` |
| `payment_condition` | null | Reserved, not yet populated |
| `service_notes` | null | Reserved, not yet populated |
| `lat` | float\|null | Geocoded |
| `lng` | float\|null | Geocoded |

---

### `customer_time_windows`

Delivery time windows per customer per weekday. Sourced from *Horarios Entrega.XLSX*.

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | PK |
| `customer_id` | int | FK → customers.id |
| `weekday` | int | 1=Mon … 5=Fri (source convention) |
| `shift` | int | 1=morning, 2=afternoon |
| `open_time` | str\|null | `HH:MM:SS` |
| `close_time` | str\|null | `HH:MM:SS` |
| `is_closed` | bool | True = customer closed that day, skip |

---

### `drivers`

One row per driver. Sourced from *Detalle entrega*.

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | PK |
| `code` | str | Driver ID natural key, e.g. `850006` |
| `name` | str\|null | Driver name |

---

### `routes`

One row per route code. Sourced from *Detalle entrega*.

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | PK |
| `code` | str | Route code natural key, e.g. `DR0006` |
| `name` | str\|null | Same as code currently |
| `zone_code` | null | Reserved |

---

### `trucks`

Truck master. Not yet bootstrapped from Excel — populated manually or via API.

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | PK |
| *(no fixed schema yet)* | | |

---

### `transports`

One row per truck per day (one full route). Sourced from *Detalle entrega*.

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | PK |
| `code` | str | Transport number natural key, e.g. `11420379` |
| `transport_date` | str\|null | ISO date `YYYY-MM-DD` |
| `route_id` | int\|null | FK → routes.id |
| `driver_id` | int\|null | FK → drivers.id |
| `truck_id` | int\|null | FK → trucks.id (null until assigned) |
| `load_number` | null | Reserved |
| `trip_number` | null | Reserved |

---

### `delivery_stops`

One row per customer stop within a transport. Sourced from *Detalle entrega* grouped by `Entrega`.

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | PK |
| `delivery_code` | str | `Entrega` number natural key |
| `transport_id` | int | FK → transports.id |
| `customer_id` | int | FK → customers.id |
| `sequence` | int | Stop order within transport (1-based) |
| `address_snapshot` | str\|null | Street at time of delivery |
| `postal_code_snapshot` | str\|null | |
| `city_snapshot` | str\|null | |
| `lat` | float\|null | Geocoded |
| `lng` | float\|null | Geocoded |

---

### `delivery_lines`

One row per product line within a stop. Sourced from *Detalle entrega*.

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | PK |
| `delivery_stop_id` | int | FK → delivery_stops.id |
| `material_id` | int | FK → materials.id |
| `quantity` | float | Quantity in `sales_unit` |
| `sales_unit` | str | `PAL` / `CAJ` / `UN` |
| `warehouse_location_code` | null | Reserved — for pick-path optimization |

---

## Entity Relationship Summary

```
warehouses
  └── warehouse_locations (warehouse_id)

material_types
  └── materials (material_type_id)
        └── material_dimensions (material_id)

customers
  └── customer_time_windows (customer_id)

drivers ──────────────────────────────┐
routes  ──────────────────────────────┤
trucks  ──────────────────────────────┤
  └── transports (driver_id, route_id, truck_id)
        └── delivery_stops (transport_id)
              ├── customers (customer_id)
              └── delivery_lines (delivery_stop_id)
                    └── materials (material_id)
```

---

## Bootstrap Row Counts (typical after full Excel import)

| Table | Approx rows |
|-------|-------------|
| warehouses | 1 |
| warehouse_locations | ~1,400 |
| material_types | 11 |
| materials | ~1,600 |
| material_dimensions | ~5,000 |
| customers | ~1,368 |
| customer_time_windows | ~1,015 |
| drivers | ~50 |
| routes | ~30 |
| trucks | 0 (not yet bootstrapped) |
| transports | ~8,900 |
| delivery_stops | ~80,000+ |
| delivery_lines | ~82,849 |
