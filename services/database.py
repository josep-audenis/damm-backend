from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = ROOT_DIR / "data" / "app_db.json"
TABLES = [
    "warehouses",
    "material_types",
    "materials",
    "material_dimensions",
    "customers",
    "customer_time_windows",
    "drivers",
    "routes",
    "trucks",
    "transports",
    "orders",
    "delivery_stops",
    "delivery_lines",
]
OBSOLETE_TABLES = ["source_documents", "source_document_lines", "warehouse_locations"]
FK_FIELDS_BY_TABLE = {
    "material_dimensions": ["material_id"],
    "customer_time_windows": ["customer_id"],
    "trucks": ["warehouse_id"],
    "transports": ["route_id", "driver_id", "truck_id"],
    "delivery_stops": ["transport_id", "customer_id"],
    "orders": ["customer_id", "material_id"],
    "delivery_lines": ["delivery_stop_id", "order_id"],
    "materials": ["material_type_id"],
}
FK_TARGET_TABLES = {
    "warehouse_id": "warehouses",
    "material_type_id": "material_types",
    "material_id": "materials",
    "customer_id": "customers",
    "driver_id": "drivers",
    "route_id": "routes",
    "truck_id": "trucks",
    "transport_id": "transports",
    "delivery_stop_id": "delivery_stops",
    "order_id": "orders",
}
TEXT_FIELDS = {"name", "name_2", "description", "city", "zone_name", "plate"}
ADDRESS_FIELDS = {"address"}
STREET_PREFIXES = {
    "CALLE": "CARRER",
    "C/": "CARRER",
    "C": "CARRER",
    "C.": "CARRER",
    "CL": "CARRER",
    "CR": "CARRER",
    "AV": "AVINGUDA",
    "AV.": "AVINGUDA",
    "AVDA": "AVINGUDA",
    "AVDA.": "AVINGUDA",
    "AVENIDA": "AVINGUDA",
    "PZ": "PLAÇA",
    "PZ.": "PLAÇA",
    "PLZ": "PLAÇA",
    "PLZ.": "PLAÇA",
    "PLAZA": "PLAÇA",
    "PLAÇA": "PLAÇA",
}
MATERIAL_TYPE_SEEDS = [
    ("beer_bottle", "Beer Bottle", "Returnable or non-returnable bottled beer"),
    ("beer_barrel", "Beer Barrel", "Keg or barrel"),
    ("water", "Water", "Water and mineral water"),
    ("soft_drink", "Soft Drink", "Carbonated or still soft drinks"),
    ("dairy", "Dairy", "Milk and dairy"),
    ("coffee", "Coffee", "Coffee and related products"),
    ("wine_spirits", "Wine & Spirits", "Wine, cava, spirits, liquor"),
    ("food", "Food", "General food products"),
    ("disposable", "Disposable", "Cups, napkins, bags, hygiene"),
    ("gas", "Gas", "Gas cylinder or siphon"),
    ("returnable_empty", "Returnable Empty", "Empty crate, bottle or returnable asset"),
]


class DatabaseService:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path

    def init_db(self) -> None:
        if not self.db_path.exists():
            db = self._empty_db()
            self._seed_material_types(db)
            self._seed_default_warehouse(db)
            self._save(db)
        else:
            db = self._load()
            migrated = self._normalize_db(db)
            migrated = self._migrate(db) or migrated
            migrated = self._seed_material_types(db) or migrated
            migrated = self._seed_default_warehouse(db) or migrated
            if migrated:
                self._save(db)

    def _empty_db(self) -> dict[str, Any]:
        return {
            "meta": {"generated_at": datetime.now(UTC).isoformat()},
            "tables": {table: [] for table in TABLES},
        }

    def _load(self) -> dict[str, Any]:
        if not self.db_path.exists():
            payload = self._empty_db()
            self._save(payload)
            return payload
        db = json.loads(self.db_path.read_text(encoding="utf-8"))
        if self._normalize_db(db):
            self._save(db)
        return db

    def _save(self, payload: dict[str, Any]) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _next_id(self, db: dict[str, Any], table: str) -> str:
        self._ensure_table(db, table)
        return str(uuid.uuid4())

    def _find_by(self, rows: list[dict[str, Any]], key: str, value: Any) -> dict[str, Any] | None:
        return next((row for row in rows if row.get(key) == value), None)

    def _normalize_db(self, db: dict[str, Any]) -> bool:
        changed = False
        if not isinstance(db.get("meta"), dict):
            db["meta"] = {"generated_at": datetime.now(UTC).isoformat()}
            changed = True
        if not isinstance(db.get("tables"), dict):
            db["tables"] = {}
            changed = True
        for table in OBSOLETE_TABLES:
            if table in db["tables"]:
                del db["tables"][table]
                changed = True
        for table in TABLES:
            changed = self._ensure_table(db, table) or changed
        for table in list(db["tables"]):
            changed = self._ensure_table(db, table) or changed
        if "seq" in db:
            del db["seq"]
            changed = True
        return changed

    def _ensure_table(self, db: dict[str, Any], table: str) -> bool:
        changed = False
        if table not in db["tables"] or not isinstance(db["tables"][table], list):
            db["tables"][table] = []
            changed = True
        return changed

    def _migrate(self, db: dict[str, Any]) -> bool:
        changed = False
        if self._migrate_delivery_line_orders(db):
            changed = True
        removed_fields = {
            "warehouses": ["code", "created_at", "storage_center_code"],
            "customer_time_windows": ["shift", "is_closed"],
            "customers": ["code", "payment_condition", "service_notes"],
            "drivers": ["code"],
            "material_types": ["code"],
            "materials": ["code", "manufacturer", "manufacturer_code", "product_hierarchy_code"],
            "transports": ["code", "load_number", "trip_number"],
            "trucks": ["code", "truck_type", "active"],
            "delivery_stops": ["delivery_code", "address_snapshot", "postal_code_snapshot", "city_snapshot"],
            "delivery_lines": ["material_id", "quantity", "sales_unit", "warehouse_location_code"],
        }
        for table, fields in removed_fields.items():
            for row in db["tables"].get(table, []):
                for field in fields:
                    if field in row:
                        del row[field]
                        changed = True
        if self._dedupe_warehouses(db):
            changed = True
        for row in db["tables"].get("warehouses", []):
            if "lat" not in row:
                row["lat"] = None
                changed = True
            if "lng" not in row:
                row["lng"] = None
                changed = True
        for row in db["tables"].get("customers", []):
            if "lat" not in row:
                row["lat"] = None
                changed = True
            if "lng" not in row:
                row["lng"] = None
                changed = True
        for row in db["tables"].get("delivery_stops", []):
            if "lat" not in row:
                row["lat"] = None
                changed = True
            if "lng" not in row:
                row["lng"] = None
                changed = True
        for row in db["tables"].get("orders", []):
            if "delivered_flag" not in row:
                row["delivered_flag"] = False
                changed = True
        if self._migrate_int_ids_to_uuids(db):
            changed = True
        if self._normalize_string_values(db):
            changed = True
        return changed

    def _migrate_int_ids_to_uuids(self, db: dict[str, Any]) -> bool:
        id_map: dict[str, dict[int, str]] = {}
        changed = False
        for table, rows in db["tables"].items():
            table_map: dict[int, str] = {}
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get("id"), int):
                    continue
                old_id = row["id"]
                new_id = self._next_id(db, table)
                row["id"] = new_id
                table_map[old_id] = new_id
                changed = True
            if table_map:
                id_map[table] = table_map

        for table, fields in FK_FIELDS_BY_TABLE.items():
            for row in db["tables"].get(table, []):
                if not isinstance(row, dict):
                    continue
                for field in fields:
                    value = row.get(field)
                    if not isinstance(value, int):
                        continue
                    target_table = FK_TARGET_TABLES[field]
                    mapped = id_map.get(target_table, {}).get(value)
                    if mapped is not None:
                        row[field] = mapped
                        changed = True
        return changed

    def _normalize_string_values(self, db: dict[str, Any]) -> bool:
        changed = False
        for rows in db["tables"].values():
            for row in rows:
                if not isinstance(row, dict):
                    continue
                normalized = self._normalize_payload(row)
                for key, value in normalized.items():
                    if row.get(key) != value:
                        row[key] = value
                        changed = True
        return changed

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        for key, value in payload.items():
            if key in ADDRESS_FIELDS:
                normalized[key] = _normalize_address(value)
            elif key in TEXT_FIELDS:
                normalized[key] = _normalize_human_text(value)
        return normalized

    def _dedupe_warehouses(self, db: dict[str, Any]) -> bool:
        seen: dict[str, Any] = {}
        remap: dict[Any, Any] = {}
        unique_rows: list[dict[str, Any]] = []
        changed = False

        for row in db["tables"].get("warehouses", []):
            row_id = row.get("id")
            name = row.get("name")
            key = str(name).strip().casefold() if name else f"id:{row_id}"
            existing_id = seen.get(key)
            if existing_id is None:
                seen[key] = row_id
                unique_rows.append(row)
                continue
            remap[row_id] = existing_id
            changed = True

        if changed:
            db["tables"]["warehouses"] = unique_rows
            for table in ["trucks"]:
                for row in db["tables"].get(table, []):
                    warehouse_id = row.get("warehouse_id")
                    if warehouse_id in remap:
                        row["warehouse_id"] = remap[warehouse_id]
        return changed

    def _migrate_delivery_line_orders(self, db: dict[str, Any]) -> bool:
        changed = False
        if not db["tables"].get("delivery_lines"):
            return changed

        stops_by_id = {
            row.get("id"): row
            for row in db["tables"].get("delivery_stops", [])
            if isinstance(row, dict)
        }
        transports_by_id = {
            row.get("id"): row
            for row in db["tables"].get("transports", [])
            if isinstance(row, dict)
        }

        for line in db["tables"]["delivery_lines"]:
            if "order_id" in line:
                continue
            stop = stops_by_id.get(line.get("delivery_stop_id"), {})
            transport = transports_by_id.get(stop.get("transport_id"), {})
            order = {
                "id": self._next_id(db, "orders"),
                "customer_id": stop.get("customer_id"),
                "due_date": transport.get("transport_date"),
                "material_id": line.get("material_id"),
                "quantity": line.get("quantity"),
                "sales_unit": line.get("sales_unit"),
                "delivered_flag": False,
            }
            db["tables"]["orders"].append(order)
            line["order_id"] = order["id"]
            changed = True
        return changed

    def _upsert(self, db: dict[str, Any], table: str, key: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_table(db, table)
        rows = db["tables"][table]
        existing = self._find_by(rows, key, payload[key])
        if existing is None:
            row = {"id": self._next_id(db, table), **self._normalize_payload(payload)}
            rows.append(row)
            return row
        existing.update({k: v for k, v in self._normalize_payload(payload).items() if v is not None})
        return existing

    def _seed_material_types(self, db: dict[str, Any]) -> bool:
        changed = False
        for _, name, description in MATERIAL_TYPE_SEEDS:
            payload = self._normalize_payload({"name": name, "description": description})
            row = self._find_by(db["tables"]["material_types"], "name", payload["name"])
            if row is None:
                db["tables"]["material_types"].append(
                    {
                        "id": self._next_id(db, "material_types"),
                        **payload,
                    }
                )
                changed = True
            elif row.get("description") != payload["description"]:
                row["description"] = payload["description"]
                changed = True
        return changed

    def _seed_default_warehouse(self, db: dict[str, Any]) -> bool:
        payload = {
            "name": "DDI MOLLET",
            "address": None,
            "postal_code": None,
            "city": "MOLLET DEL VALLÈS",
            "lat": None,
            "lng": None,
        }
        row = self._find_by(db["tables"]["warehouses"], "name", payload["name"])
        if row is None:
            db["tables"]["warehouses"].append(
                {
                    "id": self._next_id(db, "warehouses"),
                    **payload,
                }
            )
            return True
        changed = False
        for key, value in payload.items():
            if key not in row:
                row[key] = value
                changed = True
        return changed

    def list_rows(self, table: str, limit: int = 100) -> list[dict[str, Any]]:
        db = self._load()
        self._ensure_table(db, table)
        return db["tables"][table][:limit]

    def list_tables(self) -> dict[str, int]:
        db = self._load()
        return {table: len(rows) for table, rows in sorted(db["tables"].items())}

    def describe_table(self, table: str) -> dict[str, list[str]]:
        db = self._load()
        self._ensure_table(db, table)
        fields: dict[str, set[str]] = {}
        for row in db["tables"][table]:
            if not isinstance(row, dict):
                continue
            for key, value in row.items():
                fields.setdefault(key, set()).add(type(value).__name__)
        return {key: sorted(types) for key, types in sorted(fields.items())}

    def get_row(self, table: str, row_id: str) -> dict[str, Any] | None:
        db = self._load()
        self._ensure_table(db, table)
        return self._find_by(db["tables"][table], "id", row_id)

    def insert_row(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        db = self._load()
        self._ensure_table(db, table)
        row = {"id": self._next_id(db, table), **self._normalize_payload(payload)}
        db["tables"][table].append(row)
        self._save(db)
        return row

    def update_row(self, table: str, row_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        db = self._load()
        self._ensure_table(db, table)
        row = self._find_by(db["tables"][table], "id", row_id)
        if row is None:
            return None
        row.update(self._normalize_payload(payload))
        self._save(db)
        return row

    def delete_row(self, table: str, row_id: str) -> dict[str, Any] | None:
        db = self._load()
        self._ensure_table(db, table)
        rows = db["tables"][table]
        for index, row in enumerate(rows):
            if row.get("id") == row_id:
                deleted = rows.pop(index)
                self._save(db)
                return deleted
        return None

    def clear_table(self, table: str) -> int:
        db = self._load()
        self._ensure_table(db, table)
        deleted = len(db["tables"][table])
        db["tables"][table] = []
        self._save(db)
        return deleted

    def update_rows_by_field(self, table: str, field: str, value: Any, payload: dict[str, Any]) -> int:
        db = self._load()
        self._ensure_table(db, table)
        updated = 0
        for row in db["tables"][table]:
            if row.get(field) == value:
                row.update(self._normalize_payload(payload))
                updated += 1
        if updated:
            self._save(db)
        return updated


def _normalize_human_text(value: Any) -> Any:
    if value is None:
        return value
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text.upper()


def _normalize_address(value: Any) -> Any:
    text = _normalize_human_text(value)
    if not isinstance(text, str) or not text:
        return text
    match = re.match(r"^([A-ZÀ-Ü/]+\.?)(?:\s+|$)(.*)$", text)
    if match is None:
        return text
    prefix, rest = match.groups()
    normalized_prefix = STREET_PREFIXES.get(prefix)
    if normalized_prefix is None:
        return text
    return f"{normalized_prefix} {rest}".strip()


db_service = DatabaseService()
