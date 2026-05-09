from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from models.domain import ProductUnit
from services.data_loader import DEFAULT_RAW_DIR, _categorize_product, _clean_id, _clean_text, _is_returnable


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
BOOTSTRAP_TABLES = [
    "material_types",
    "materials",
    "material_dimensions",
    "customers",
    "customer_time_windows",
    "drivers",
    "routes",
    "transports",
    "orders",
    "delivery_stops",
    "delivery_lines",
]
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
    def __init__(self, db_path: Path = DB_PATH, raw_dir: Path = DEFAULT_RAW_DIR) -> None:
        self.db_path = db_path
        self.raw_dir = raw_dir

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

    def _reset_bootstrap_tables(self, db: dict[str, Any]) -> None:
        for table in BOOTSTRAP_TABLES:
            db["tables"][table] = []
        self._seed_material_types(db)

    def bootstrap_from_excels(self) -> dict[str, int]:
        self.init_db()
        db = self._load()

        hackaton_path = self.raw_dir / "Hackaton.xlsx"
        horarios_path = self.raw_dir / "Horarios Entrega.XLSX"
        zm040_path = self.raw_dir / "ZM040.XLSX"

        detail_df = pd.read_excel(hackaton_path, sheet_name="Detalle entrega")
        address_df = pd.read_excel(hackaton_path, sheet_name="Direcciones")
        zones_df = pd.read_excel(hackaton_path, sheet_name="ZONAS")
        locations_df = pd.read_excel(hackaton_path, sheet_name="Materiales zubic")
        schedule_df = pd.read_excel(horarios_path)
        dimensions_df = pd.read_excel(zm040_path)

        self._reset_bootstrap_tables(db)
        customer_map = self._bootstrap_customers(db, address_df, zones_df)
        transport_map = self._bootstrap_drivers_routes_transports(db, detail_df)
        material_map = self._bootstrap_materials(db, detail_df, locations_df, dimensions_df)
        self._bootstrap_time_windows(db, schedule_df, customer_map)
        self._bootstrap_delivery_stops_and_lines(db, detail_df, customer_map, transport_map, material_map)
        db["meta"]["generated_at"] = datetime.now(UTC).isoformat()
        self._save(db)
        return {table: len(db["tables"][table]) for table in TABLES}

    def _bootstrap_customers(
        self,
        db: dict[str, Any],
        address_df: pd.DataFrame,
        zones_df: pd.DataFrame,
    ) -> dict[str, str]:
        customer_map: dict[str, str] = {}
        zone_map: dict[str, tuple[str | None, str | None]] = {}
        for _, row in zones_df.iterrows():
            customer_code = _clean_id(row.get("cliente zona"))
            if customer_code:
                zone_map[customer_code] = (
                    _clean_text(row.get("ZonaTransp") or row.get("ZONAS")),
                    _normalize_human_text(row.get("Zona Entrega") or row.get("NOMBRE ZONAS")),
                )
        for _, row in address_df.iterrows():
            customer_code = _clean_id(row["Cliente"])
            if not customer_code or customer_code in customer_map:
                continue
            zone_code, zone_name = zone_map.get(customer_code, (None, None))
            customer = {
                "id": self._next_id(db, "customers"),
                "name": _normalize_human_text(row["Nombre 1"] or row["Nombre 2"]),
                "name_2": _normalize_human_text(row["Nombre 2"]),
                "address": _normalize_address(row["Calle"]),
                "postal_code": _clean_id(row["CP"]),
                "city": _normalize_human_text(row["Población"]),
                "zone_code": zone_code,
                "zone_name": zone_name,
                "lat": None,
                "lng": None,
            }
            db["tables"]["customers"].append(customer)
            customer_map[customer_code] = customer["id"]
        return customer_map

    def _bootstrap_drivers_routes_transports(self, db: dict[str, Any], detail_df: pd.DataFrame) -> dict[str, str]:
        driver_map: dict[str, str] = {}
        transport_map: dict[str, str] = {}
        for _, row in (
            detail_df[["Repartidor", "Destinatario mcía.", "Ruta", "Transporte", "FECHA"]]
            .drop_duplicates(subset=["Transporte"])
            .iterrows()
        ):
            driver_code = _clean_id(row["Repartidor"])
            route_code = _clean_text(row["Ruta"])
            transport_code = _clean_id(row["Transporte"])
            transport_date = pd.to_datetime(row["FECHA"], dayfirst=True, errors="coerce")
            driver_id = driver_map.get(driver_code)
            if driver_id is None:
                driver = {
                    "id": self._next_id(db, "drivers"),
                    "name": _normalize_human_text(row["Destinatario mcía."]),
                }
                db["tables"]["drivers"].append(driver)
                driver_id = driver["id"]
                driver_map[driver_code] = driver_id
            route = self._upsert(
                db,
                "routes",
                "code",
                {"code": route_code, "name": route_code, "zone_code": None},
            )
            transport = {
                "id": self._next_id(db, "transports"),
                "transport_date": transport_date.date().isoformat() if pd.notna(transport_date) else None,
                "route_id": route["id"],
                "driver_id": driver_id,
                "truck_id": None,
            }
            db["tables"]["transports"].append(transport)
            transport_map[transport_code] = transport["id"]
        return transport_map

    def _bootstrap_materials(
        self,
        db: dict[str, Any],
        detail_df: pd.DataFrame,
        locations_df: pd.DataFrame,
        dimensions_df: pd.DataFrame,
    ) -> dict[str, str]:
        material_map: dict[str, str] = {}
        location_lookup: dict[str, dict[str, str]] = {}
        for _, row in locations_df.iterrows():
            code = _clean_text(row["Material"])
            if code:
                location_lookup[code] = {
                    "base_unit": _clean_text(row["UMB"]),
                    "location": _clean_text(row["Ubic."]),
                    "storage_center": _clean_text(row["Ce."]),
                    "section": _clean_text(row["Alm."]),
                }
        material_type_map = {
            code: row["id"]
            for code, name, _ in MATERIAL_TYPE_SEEDS
            if (row := self._find_by(db["tables"]["material_types"], "name", _normalize_human_text(name))) is not None
        }
        for material, description, sales_unit in (
            detail_df[["Material", "Denominación", "Un.medida venta"]]
            .drop_duplicates(subset=["Material"])
            .itertuples(index=False)
        ):
            material_code = _clean_text(material)
            description_text = _clean_text(description)
            sales_unit_text = _clean_text(sales_unit)
            try:
                sales_unit_enum = ProductUnit(sales_unit_text)
            except ValueError:
                sales_unit_enum = ProductUnit.UN
            category_code = _categorize_product(material_code, description_text, sales_unit_enum).value
            location = location_lookup.get(material_code, {})
            material_row = {
                "id": self._next_id(db, "materials"),
                "description": _normalize_human_text(description_text),
                "base_unit": location.get("base_unit") or sales_unit_text,
                "material_type_id": material_type_map.get(category_code),
                "is_returnable": _is_returnable(material_code, description_text),
            }
            db["tables"]["materials"].append(material_row)
            material_map[material_code] = material_row["id"]
            for _, dim_row in dimensions_df[dimensions_df["Material"] == material_code].iterrows():
                unit = _clean_text(dim_row["UMA"])
                if not unit:
                    continue
                existing = next(
                    (
                        row
                        for row in db["tables"]["material_dimensions"]
                        if row["material_id"] == material_row["id"] and row["unit"] == unit
                    ),
                    None,
                )
                payload = {
                    "material_id": material_row["id"],
                    "unit": unit,
                    "counter": int(dim_row["Contador"]) if pd.notna(dim_row["Contador"]) else None,
                    "length_cm": self._normalize_length(dim_row["Longitud"], dim_row["Unidad dimensión"]),
                    "width_cm": self._normalize_length(
                        dim_row["Ancho"],
                        dim_row.get("Unidad dimensión.1", dim_row["Unidad dimensión"]),
                    ),
                    "height_cm": self._normalize_length(
                        dim_row["Altura"],
                        dim_row.get("Unidad dimensión.2", dim_row["Unidad dimensión"]),
                    ),
                    "volume_l": float(dim_row["Volumen"]) if pd.notna(dim_row["Volumen"]) and dim_row["Volumen"] else None,
                    "weight_gross_kg": self._normalize_weight(dim_row["Peso bruto"], dim_row["Un"]),
                    "weight_net_kg": self._normalize_weight(
                        dim_row["Peso neto"],
                        dim_row.get("Un.2", dim_row["Un"]),
                    ),
                }
                if existing is None:
                    db["tables"]["material_dimensions"].append(
                        {"id": self._next_id(db, "material_dimensions"), **payload}
                    )
                else:
                    existing.update(payload)
        return material_map

    def _bootstrap_time_windows(
        self,
        db: dict[str, Any],
        schedule_df: pd.DataFrame,
        customer_map: dict[str, str],
    ) -> None:
        for _, row in schedule_df.iterrows():
            customer_id = customer_map.get(_clean_id(row["Deudor"]))
            if customer_id is None:
                continue
            payload = {
                "customer_id": customer_id,
                "weekday": int(row["Día semana"]) if pd.notna(row["Día semana"]) else 0,
                "open_time": self._normalize_time(row["Horario inicia a"]),
                "close_time": self._normalize_time(row["Horario termina a"]),
            }
            existing = next(
                (
                    item
                    for item in db["tables"]["customer_time_windows"]
                    if item["customer_id"] == payload["customer_id"]
                    and item["weekday"] == payload["weekday"]
                    and item["open_time"] == payload["open_time"]
                    and item["close_time"] == payload["close_time"]
                ),
                None,
            )
            if existing is None:
                db["tables"]["customer_time_windows"].append(
                    {"id": self._next_id(db, "customer_time_windows"), **payload}
                )
            else:
                existing.update(payload)

    def _bootstrap_delivery_stops_and_lines(
        self,
        db: dict[str, Any],
        detail_df: pd.DataFrame,
        customer_map: dict[str, str],
        transport_map: dict[str, str],
        material_map: dict[str, str],
    ) -> None:
        detail_df = detail_df.copy()
        detail_df["_source_order"] = range(len(detail_df))
        for transport_code, transport_rows in detail_df.groupby("Transporte", sort=False):
            transport_id = transport_map.get(_clean_id(transport_code))
            if transport_id is None:
                continue
            ordered_rows = transport_rows.sort_values("_source_order")
            for sequence, (_, stop_rows) in enumerate(
                ordered_rows.groupby("Entrega", sort=False),
                start=1,
            ):
                first = stop_rows.iloc[0]
                customer_id = customer_map.get(_clean_id(first["Destinatario mcía..1"]))
                if customer_id is None:
                    continue
                stop_row = {
                    "id": self._next_id(db, "delivery_stops"),
                    "transport_id": transport_id,
                    "customer_id": customer_id,
                    "sequence": sequence,
                    "lat": None,
                    "lng": None,
                }
                db["tables"]["delivery_stops"].append(stop_row)
                due_date = pd.to_datetime(first["FECHA"], dayfirst=True, errors="coerce")
                for _, line in stop_rows.iterrows():
                    material_id = material_map.get(_clean_text(line["Material"]))
                    if material_id is None:
                        continue
                    order = {
                        "id": self._next_id(db, "orders"),
                        "customer_id": customer_id,
                        "due_date": due_date.date().isoformat() if pd.notna(due_date) else None,
                        "material_id": material_id,
                        "quantity": float(line["Cantidad entrega"]) if pd.notna(line["Cantidad entrega"]) else 0.0,
                        "sales_unit": _clean_text(line["Un.medida venta"]),
                        "delivered_flag": False,
                    }
                    db["tables"]["orders"].append(order)
                    db["tables"]["delivery_lines"].append(
                        {
                            "id": self._next_id(db, "delivery_lines"),
                            "delivery_stop_id": stop_row["id"],
                            "order_id": order["id"],
                        }
                    )

    def _normalize_length(self, value: Any, unit: Any) -> float | None:
        if pd.isna(value):
            return None
        raw = float(value)
        if raw <= 0:
            return None
        normalized_unit = _clean_text(unit).upper()
        if normalized_unit == "MM":
            return raw / 10
        if normalized_unit == "M":
            return raw * 100
        return raw

    def _normalize_weight(self, value: Any, unit: Any) -> float | None:
        if pd.isna(value):
            return None
        raw = float(value)
        if raw <= 0:
            return None
        normalized_unit = _clean_text(unit).upper()
        if normalized_unit in {"G", "GR"}:
            return raw / 1000
        return raw

    def _normalize_time(self, value: Any) -> str | None:
        if pd.isna(value):
            return None
        parsed = pd.to_datetime(str(value), errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.time().replace(microsecond=0).isoformat()

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
    try:
        if pd.isna(value):
            return value
    except (TypeError, ValueError):
        pass
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
