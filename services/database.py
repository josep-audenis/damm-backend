from __future__ import annotations

import json
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
    "warehouse_locations",
    "material_types",
    "materials",
    "material_dimensions",
    "customers",
    "customer_time_windows",
    "drivers",
    "routes",
    "trucks",
    "transports",
    "delivery_stops",
    "delivery_lines",
]


class DatabaseService:
    def __init__(self, db_path: Path = DB_PATH, raw_dir: Path = DEFAULT_RAW_DIR) -> None:
        self.db_path = db_path
        self.raw_dir = raw_dir

    def init_db(self) -> None:
        if not self.db_path.exists():
            self._save(self._empty_db())
            self._seed_material_types()
            self._seed_default_warehouse()
        else:
            db = self._load()
            migrated = self._normalize_db(db)
            migrated = self._migrate(db) or migrated
            if migrated:
                self._save(db)

    def _empty_db(self) -> dict[str, Any]:
        return {
            "meta": {"generated_at": datetime.now(UTC).isoformat()},
            "seq": {table: 0 for table in TABLES},
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

    def _next_id(self, db: dict[str, Any], table: str) -> int:
        self._ensure_table(db, table)
        db["seq"][table] += 1
        return int(db["seq"][table])

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
        if not isinstance(db.get("seq"), dict):
            db["seq"] = {}
            changed = True
        for table in TABLES:
            changed = self._ensure_table(db, table) or changed
        for table in list(db["tables"]):
            changed = self._ensure_table(db, table) or changed
        return changed

    def _ensure_table(self, db: dict[str, Any], table: str) -> bool:
        changed = False
        if table not in db["tables"] or not isinstance(db["tables"][table], list):
            db["tables"][table] = []
            changed = True
        max_id = max(
            (int(row["id"]) for row in db["tables"][table] if isinstance(row, dict) and isinstance(row.get("id"), int)),
            default=0,
        )
        current_seq = db["seq"].get(table)
        if not isinstance(current_seq, int) or current_seq < max_id:
            db["seq"][table] = max_id
            changed = True
        return changed

    def _migrate(self, db: dict[str, Any]) -> bool:
        changed = False
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
        for row in db["tables"].get("warehouse_locations", []):
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
        return changed

    def _upsert(self, db: dict[str, Any], table: str, key: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_table(db, table)
        rows = db["tables"][table]
        existing = self._find_by(rows, key, payload[key])
        if existing is None:
            row = {"id": self._next_id(db, table), **payload}
            rows.append(row)
            return row
        existing.update({k: v for k, v in payload.items() if v is not None})
        return existing

    def _seed_material_types(self) -> None:
        db = self._load()
        rows = [
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
        for code, name, description in rows:
            self._upsert(
                db,
                "material_types",
                "code",
                {"code": code, "name": name, "description": description},
            )
        self._save(db)

    def _seed_default_warehouse(self) -> None:
        db = self._load()
        self._upsert(
            db,
            "warehouses",
            "code",
            {
                "code": "D131",
                "name": "DDI Mollet",
                "storage_center_code": "D131",
                "address": None,
                "postal_code": None,
                "city": "Mollet del Vallès",
                "lat": None,
                "lng": None,
                "created_at": datetime.now(UTC).isoformat(),
            },
        )
        self._save(db)

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

        self._bootstrap_customers(db, address_df, zones_df)
        self._bootstrap_drivers_routes_transports(db, detail_df)
        self._bootstrap_materials(db, detail_df, locations_df, dimensions_df)
        self._bootstrap_time_windows(db, schedule_df)
        self._bootstrap_delivery_stops_and_lines(db, detail_df)
        db["meta"]["generated_at"] = datetime.now(UTC).isoformat()
        self._save(db)
        return {table: len(db["tables"][table]) for table in TABLES}

    def _bootstrap_customers(
        self,
        db: dict[str, Any],
        address_df: pd.DataFrame,
        zones_df: pd.DataFrame,
    ) -> None:
        zone_map: dict[str, tuple[str | None, str | None]] = {}
        for _, row in zones_df.iterrows():
            customer_code = _clean_id(row.get("cliente zona"))
            if customer_code:
                zone_map[customer_code] = (
                    _clean_text(row.get("ZonaTransp") or row.get("ZONAS")),
                    _clean_text(row.get("Zona Entrega") or row.get("NOMBRE ZONAS")),
                )
        for _, row in address_df.iterrows():
            customer_code = _clean_id(row["Cliente"])
            if not customer_code:
                continue
            zone_code, zone_name = zone_map.get(customer_code, (None, None))
            self._upsert(
                db,
                "customers",
                "code",
                {
                    "code": customer_code,
                    "name": _clean_text(row["Nombre 1"] or row["Nombre 2"]),
                    "name_2": _clean_text(row["Nombre 2"]),
                    "address": _clean_text(row["Calle"]),
                    "postal_code": _clean_id(row["CP"]),
                    "city": _clean_text(row["Población"]),
                    "zone_code": zone_code,
                    "zone_name": zone_name,
                    "payment_condition": None,
                    "service_notes": None,
                    "lat": None,
                    "lng": None,
                },
            )

    def _bootstrap_drivers_routes_transports(self, db: dict[str, Any], detail_df: pd.DataFrame) -> None:
        for _, row in (
            detail_df[["Repartidor", "Destinatario mcía.", "Ruta", "Transporte", "FECHA"]]
            .drop_duplicates(subset=["Transporte"])
            .iterrows()
        ):
            driver_code = _clean_id(row["Repartidor"])
            route_code = _clean_text(row["Ruta"])
            transport_code = _clean_id(row["Transporte"])
            transport_date = pd.to_datetime(row["FECHA"], dayfirst=True, errors="coerce")
            driver = self._upsert(
                db,
                "drivers",
                "code",
                {"code": driver_code, "name": _clean_text(row["Destinatario mcía."])},
            )
            route = self._upsert(
                db,
                "routes",
                "code",
                {"code": route_code, "name": route_code, "zone_code": None},
            )
            self._upsert(
                db,
                "transports",
                "code",
                {
                    "code": transport_code,
                    "transport_date": transport_date.date().isoformat() if pd.notna(transport_date) else None,
                    "route_id": route["id"],
                    "driver_id": driver["id"],
                    "truck_id": None,
                    "load_number": None,
                    "trip_number": None,
                },
            )

    def _bootstrap_materials(
        self,
        db: dict[str, Any],
        detail_df: pd.DataFrame,
        locations_df: pd.DataFrame,
        dimensions_df: pd.DataFrame,
    ) -> None:
        warehouse = self._find_by(db["tables"]["warehouses"], "code", "D131")
        location_lookup: dict[str, dict[str, str]] = {}
        for _, row in locations_df.iterrows():
            code = _clean_text(row["Material"])
            if code:
                location_lookup[code] = {
                    "base_unit": _clean_text(row["UMB"]),
                    "manufacturer": _clean_text(row["Fabricante"]),
                    "manufacturer_code": _clean_text(row["Número de un fabricante"]),
                    "location": _clean_text(row["Ubic."]),
                    "storage_center": _clean_text(row["Ce."]),
                    "section": _clean_text(row["Alm."]),
                }
        material_type_map = {row["code"]: row["id"] for row in db["tables"]["material_types"]}
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
            material_row = self._upsert(
                db,
                "materials",
                "code",
                {
                    "code": material_code,
                    "description": description_text,
                    "base_unit": location.get("base_unit") or sales_unit_text,
                    "material_type_id": material_type_map.get(category_code),
                    "manufacturer": location.get("manufacturer"),
                    "manufacturer_code": location.get("manufacturer_code"),
                    "product_hierarchy_code": None,
                    "is_returnable": _is_returnable(material_code, description_text),
                },
            )
            if location.get("location") and warehouse is not None:
                self._upsert(
                    db,
                    "warehouse_locations",
                    "code",
                    {
                        "warehouse_id": warehouse["id"],
                        "code": location["location"],
                        "storage_center_code": location.get("storage_center"),
                        "warehouse_section": location.get("section"),
                        "base_unit": location.get("base_unit"),
                        "manufacturer": location.get("manufacturer"),
                        "manufacturer_code": location.get("manufacturer_code"),
                        "lat": None,
                        "lng": None,
                    },
                )
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
                hierarchy_code = _clean_text(dim_row.get("Jquía.productos"))
                if hierarchy_code:
                    material_row["product_hierarchy_code"] = hierarchy_code

    def _bootstrap_time_windows(self, db: dict[str, Any], schedule_df: pd.DataFrame) -> None:
        customer_map = {row["code"]: row["id"] for row in db["tables"]["customers"]}
        for _, row in schedule_df.iterrows():
            customer_id = customer_map.get(_clean_id(row["Deudor"]))
            if customer_id is None:
                continue
            payload = {
                "customer_id": customer_id,
                "weekday": int(row["Día semana"]) if pd.notna(row["Día semana"]) else 0,
                "shift": int(row["Turno"]) if pd.notna(row["Turno"]) else 1,
                "open_time": self._normalize_time(row["Horario inicia a"]),
                "close_time": self._normalize_time(row["Horario termina a"]),
                "is_closed": _clean_text(row["Cierre Si/No"]).upper() == "X",
            }
            existing = next(
                (
                    item
                    for item in db["tables"]["customer_time_windows"]
                    if item["customer_id"] == payload["customer_id"]
                    and item["weekday"] == payload["weekday"]
                    and item["shift"] == payload["shift"]
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

    def _bootstrap_delivery_stops_and_lines(self, db: dict[str, Any], detail_df: pd.DataFrame) -> None:
        customer_map = {row["code"]: row["id"] for row in db["tables"]["customers"]}
        transport_map = {row["code"]: row["id"] for row in db["tables"]["transports"]}
        material_map = {row["code"]: row["id"] for row in db["tables"]["materials"]}
        detail_df = detail_df.copy()
        detail_df["_source_order"] = range(len(detail_df))
        for transport_code, transport_rows in detail_df.groupby("Transporte", sort=False):
            transport_id = transport_map.get(_clean_id(transport_code))
            if transport_id is None:
                continue
            ordered_rows = transport_rows.sort_values("_source_order")
            for sequence, (delivery_code, stop_rows) in enumerate(
                ordered_rows.groupby("Entrega", sort=False),
                start=1,
            ):
                first = stop_rows.iloc[0]
                customer_id = customer_map.get(_clean_id(first["Destinatario mcía..1"]))
                if customer_id is None:
                    continue
                stop_row = self._upsert(
                    db,
                    "delivery_stops",
                    "delivery_code",
                    {
                        "delivery_code": _clean_id(delivery_code),
                        "transport_id": transport_id,
                        "customer_id": customer_id,
                        "sequence": sequence,
                        "address_snapshot": _clean_text(first["Calle"]),
                        "postal_code_snapshot": _clean_id(first["CP"]),
                        "city_snapshot": _clean_text(first["Población"]),
                        "lat": None,
                        "lng": None,
                    },
                )
                for _, line in stop_rows.iterrows():
                    material_id = material_map.get(_clean_text(line["Material"]))
                    if material_id is None:
                        continue
                    payload = {
                        "delivery_stop_id": stop_row["id"],
                        "material_id": material_id,
                        "quantity": float(line["Cantidad entrega"]) if pd.notna(line["Cantidad entrega"]) else 0.0,
                        "sales_unit": _clean_text(line["Un.medida venta"]),
                        "warehouse_location_code": None,
                    }
                    existing = next(
                        (
                            item
                            for item in db["tables"]["delivery_lines"]
                            if item["delivery_stop_id"] == payload["delivery_stop_id"]
                            and item["material_id"] == payload["material_id"]
                            and item["sales_unit"] == payload["sales_unit"]
                        ),
                        None,
                    )
                    if existing is None:
                        db["tables"]["delivery_lines"].append(
                            {"id": self._next_id(db, "delivery_lines"), **payload}
                        )
                    else:
                        existing["quantity"] = payload["quantity"]

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

    def get_row(self, table: str, row_id: int) -> dict[str, Any] | None:
        db = self._load()
        self._ensure_table(db, table)
        return self._find_by(db["tables"][table], "id", row_id)

    def insert_row(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        db = self._load()
        self._ensure_table(db, table)
        row = {"id": self._next_id(db, table), **payload}
        db["tables"][table].append(row)
        self._save(db)
        return row

    def update_row(self, table: str, row_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
        db = self._load()
        self._ensure_table(db, table)
        row = self._find_by(db["tables"][table], "id", row_id)
        if row is None:
            return None
        row.update(payload)
        self._save(db)
        return row

    def delete_row(self, table: str, row_id: int) -> dict[str, Any] | None:
        db = self._load()
        self._ensure_table(db, table)
        rows = db["tables"][table]
        for index, row in enumerate(rows):
            if row.get("id") == row_id:
                deleted = rows.pop(index)
                self._save(db)
                return deleted
        return None

    def update_rows_by_field(self, table: str, field: str, value: Any, payload: dict[str, Any]) -> int:
        db = self._load()
        self._ensure_table(db, table)
        updated = 0
        for row in db["tables"][table]:
            if row.get(field) == value:
                row.update(payload)
                updated += 1
        if updated:
            self._save(db)
        return updated


db_service = DatabaseService()
