# 2026-05-09 Simplified JSON Database Schema

**Status:** accepted

## Context

The JSON database stored several source identifiers and unused fields that are no longer part of the desired app data model. These fields made the persisted schema broader than the UI and optimization flows need.

## Decision

Use the stored UUID `id` as the identity for customers, drivers, material types, materials, transports, and trucks. Source workbook identifiers are no longer persisted or required at runtime.

Remove:

- `warehouse_locations`
- `warehouses.code`
- `warehouses.created_at`
- `warehouses.storage_center_code`
- `customer_time_windows.shift`
- `customer_time_windows.is_closed`
- `customers.code`
- `customers.payment_condition`
- `customers.service_notes`
- `drivers.code`
- `material_types.code`
- `materials.code`
- `materials.manufacturer`
- `materials.manufacturer_code`
- `materials.product_hierarchy_code`
- `transports.code`
- `transports.load_number`
- `transports.trip_number`
- `delivery_stops.delivery_code`
- `delivery_stops.address_snapshot`
- `delivery_stops.postal_code_snapshot`
- `delivery_stops.city_snapshot`
- `delivery_lines.material_id`
- `delivery_lines.quantity`
- `delivery_lines.sales_unit`
- `delivery_lines.warehouse_location_code`
- `source_documents`
- `source_document_lines`

Truck rows now store only `id`, `plate`, `capacity_pallets`, and `warehouse_id`.

Add `orders` as the owner of ordered material quantities. Order rows store `id`, `customer_id`, `due_date`, `material_id`, `quantity`, `sales_unit`, and `delivered_flag`. Delivery lines now only assign an order to a delivery stop with `delivery_stop_id` and `order_id`.

## Frontend Impact

Catalog screens and clients should not expect the removed fields from `/api/v1/catalog/*` or `/api/v1/db/*` responses. Warehouse create payloads should omit `code` and `storage_center_code`. Truck create payloads should send only `plate`, `capacity_pallets`, and `warehouse_id`. Consumers that need item quantities should read them through `orders`, not `delivery_lines`.

## Backend Impact

`data/app_db.json` is the runtime source of truth. The API no longer reads raw Excel workbooks or exposes a bootstrap endpoint.

## Migration Notes

`DatabaseService.init_db()` removes obsolete tables and fields from existing JSON databases. During migration, each old delivery line gets a matching order before the old line fields are stripped.
