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
  "tables": { "<table>": [ <row>, ... ], ... }
}
```

All rows have UUID4 string `id` values as primary keys. Foreign keys are UUID string `id` references (not natural keys). Imported human-facing strings are normalized to uppercase; address street prefixes use conservative Catalan forms such as `CARRER`, `AVINGUDA`, and `PLAÇA`.

---

## Tables

### `warehouses`

One row per physical warehouse/depot.

| Field | Type | Notes |
|-------|------|-------|
| `id` | str | UUID PK |
| `name` | str | e.g. `DDI MOLLET` |
| `address` | str\|null | Street address |
| `postal_code` | str\|null | |
| `city` | str\|null | e.g. `Mollet del Vallès` |
| `lat` | float\|null | Geocoded latitude |
| `lng` | float\|null | Geocoded longitude |

Seeded on init: one row for DDI Mollet.

---

### `material_types`

Lookup table — product categories. Seeded on init, not imported from Excel.

| Field | Type | Notes |
|-------|------|-------|
| `id` | str | UUID PK |
| `name` | str | Display name |
| `description` | str | |

Seeded rows: BEER BOTTLE, BEER BARREL, WATER, SOFT DRINK, DAIRY, COFFEE, WINE & SPIRITS, FOOD, DISPOSABLE, GAS, RETURNABLE EMPTY.

---

### `materials`

One row per SKU. Sourced from *Detalle entrega* + *Materiales zubic* + *ZM040*.

| Field | Type | Notes |
|-------|------|-------|
| `id` | str | UUID PK |
| `description` | str | Product name |
| `base_unit` | str\|null | `CAJ` / `PAL` / `UN` |
| `material_type_id` | str\|null | FK → material_types.id |
| `is_returnable` | bool | True if bottle/crate must be returned |

Source SKU codes are used during import to build relationships, but are not stored in `materials`.

---

### `material_dimensions`

Physical dimensions per packaging unit. Multiple rows per material (one per unit type). Sourced from *ZM040*.

| Field | Type | Notes |
|-------|------|-------|
| `id` | str | UUID PK |
| `material_id` | str | FK → materials.id |
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
| `id` | str | UUID PK |
| `name` | str\|null | Primary name (`Nombre 1`) |
| `name_2` | str\|null | Secondary name (`Nombre 2`) |
| `address` | str\|null | Street (`Calle`) |
| `postal_code` | str\|null | `CP` |
| `city` | str\|null | `Población` |
| `zone_code` | str\|null | Zone code, e.g. `DD13100002` |
| `zone_name` | str\|null | Zone name, e.g. `MOLLET PLANA LLADO` |
| `lat` | float\|null | Geocoded |
| `lng` | float\|null | Geocoded |

Source customer codes are used during import to deduplicate customers and build foreign keys, but are not stored in `customers`.

---

### `customer_time_windows`

Delivery time windows per customer per weekday. Sourced from *Horarios Entrega.XLSX*.

| Field | Type | Notes |
|-------|------|-------|
| `id` | str | UUID PK |
| `customer_id` | str | FK → customers.id |
| `weekday` | int | 1=Mon … 5=Fri (source convention) |
| `open_time` | str\|null | `HH:MM:SS` |
| `close_time` | str\|null | `HH:MM:SS` |

---

### `drivers`

One row per driver. Sourced from *Detalle entrega*.

| Field | Type | Notes |
|-------|------|-------|
| `id` | str | UUID PK |
| `name` | str\|null | Driver name |

---

### `routes`

One row per route code. Sourced from *Detalle entrega*.

| Field | Type | Notes |
|-------|------|-------|
| `id` | str | UUID PK |
| `code` | str | Route code natural key, e.g. `DR0006` |
| `name` | str\|null | Same as code currently |
| `zone_code` | null | Reserved |

---

### `trucks`

Truck master. Not yet bootstrapped from Excel — populated manually or via API.

| Field | Type | Notes |
|-------|------|-------|
| `id` | str | UUID PK |
| `plate` | str\|null | Vehicle plate |
| `capacity_pallets` | int | Pallet capacity |
| `warehouse_id` | str\|null | FK → warehouses.id |

---

### `transports`

One row per truck per day (one full route). Sourced from *Detalle entrega*.

| Field | Type | Notes |
|-------|------|-------|
| `id` | str | UUID PK |
| `transport_date` | str\|null | ISO date `YYYY-MM-DD` |
| `route_id` | str\|null | FK → routes.id |
| `driver_id` | str\|null | FK → drivers.id |
| `truck_id` | str\|null | FK → trucks.id (null until assigned) |

Source transport numbers are used during import to group deliveries, but are not stored in `transports`.

---

### `delivery_stops`

One row per customer stop within a transport. Sourced from *Detalle entrega* grouped by `Entrega`.

| Field | Type | Notes |
|-------|------|-------|
| `id` | str | UUID PK |
| `transport_id` | str | FK → transports.id |
| `customer_id` | str | FK → customers.id |
| `sequence` | int | Stop order within transport (1-based) |
| `lat` | float\|null | Geocoded |
| `lng` | float\|null | Geocoded |

---

### `orders`

One row per material quantity ordered by a customer for a due date. Sourced from *Detalle entrega* line rows.

| Field | Type | Notes |
|-------|------|-------|
| `id` | str | UUID PK |
| `customer_id` | str | FK → customers.id |
| `due_date` | str\|null | ISO date `YYYY-MM-DD` |
| `material_id` | str | FK → materials.id |
| `quantity` | float | Quantity in `sales_unit` |
| `sales_unit` | str | Source unit such as `PAL`, `CAJ`, `UN` |
| `delivered_flag` | bool | `false` when pending delivery, `true` after delivered |

---

### `delivery_lines`

One row assigning an order to a delivery stop.

| Field | Type | Notes |
|-------|------|-------|
| `id` | str | UUID PK |
| `delivery_stop_id` | str | FK → delivery_stops.id |
| `order_id` | str | FK → orders.id |

---

## Entity Relationship Summary

```
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
              └── delivery_lines (delivery_stop_id, order_id)

customers ───────────────┐
materials ───────────────┤
  └── orders (customer_id, material_id)
```

---

## Checked-in Demo Row Counts

The checked-in `data/app_db.json` is reduced for demo use. It keeps 200 randomly selected customers with complete address fields and no `S/N` addresses, plus only related rows.

| Table | Rows |
|-------|-------------|
| warehouses | 1 |
| material_types | 11 |
| materials | 773 |
| material_dimensions | 5,188 |
| customers | 200 |
| customer_time_windows | 97 |
| drivers | 18 |
| routes | 18 |
| trucks | 1 |
| transports | 598 |
| orders | 12,194 |
| delivery_stops | 1,598 |
| delivery_lines | 12,194 |

`warehouse_locations`, `source_documents`, and `source_document_lines` are obsolete and are removed by database migration.
