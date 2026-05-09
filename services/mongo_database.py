"""MongoDB-backed database service.

Implements the same public interface as DatabaseService (services/database.py)
so routers require zero changes. Uses pymongo; collections map 1-to-1 with the
JSON tables. Integer `id` fields are preserved for API compatibility — we store
them alongside MongoDB's native _id.
"""
from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from models.domain import ProductUnit
from services.data_loader import DEFAULT_RAW_DIR, _categorize_product, _clean_id, _clean_text, _is_returnable

import pandas as pd
from pathlib import Path

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

_COUNTERS_COLLECTION = "_seq"


class MongoDatabaseService:
    """Drop-in replacement for DatabaseService backed by MongoDB Atlas."""

    def __init__(
        self,
        uri: str,
        db_name: str = "damm_smart_truck",
        raw_dir: Path = DEFAULT_RAW_DIR,
    ) -> None:
        self._client: MongoClient = MongoClient(uri)
        self._db: Database = self._client[db_name]
        self.raw_dir = raw_dir

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _col(self, table: str) -> Collection:
        return self._db[table]

    def _next_id(self, table: str) -> int:
        result = self._db[_COUNTERS_COLLECTION].find_one_and_update(
            {"_id": table},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=True,
        )
        return int(result["seq"])

    def _strip_mongo(self, doc: dict[str, Any] | None) -> dict[str, Any] | None:
        if doc is None:
            return None
        doc.pop("_id", None)
        return doc

    def _find_by(self, table: str, key: str, value: Any) -> dict[str, Any] | None:
        return self._strip_mongo(self._col(table).find_one({key: value}, {"_id": 0}))

    def _upsert(self, table: str, key: str, payload: dict[str, Any]) -> dict[str, Any]:
        existing = self._find_by(table, key, payload[key])
        if existing is None:
            row = {"id": self._next_id(table), **payload}
            self._col(table).insert_one({**row})
            return row
        update_fields = {k: v for k, v in payload.items() if v is not None}
        self._col(table).update_one({key: payload[key]}, {"$set": update_fields})
        existing.update(update_fields)
        return existing

    # ------------------------------------------------------------------
    # Public API (mirrors DatabaseService exactly)
    # ------------------------------------------------------------------

    def init_db(self) -> None:
        """Ensure counters and seed data exist."""
        if self._col("material_types").count_documents({}) == 0:
            self._seed_material_types()
        if self._col("warehouses").count_documents({}) == 0:
            self._seed_default_warehouse()

    def list_tables(self) -> dict[str, int]:
        return {table: self._col(table).count_documents({}) for table in sorted(TABLES)}

    def describe_table(self, table: str) -> dict[str, list[str]]:
        fields: dict[str, set[str]] = {}
        for doc in self._col(table).find({}, {"_id": 0}).limit(200):
            for key, value in doc.items():
                fields.setdefault(key, set()).add(type(value).__name__)
        return {key: sorted(types) for key, types in sorted(fields.items())}

    def list_rows(self, table: str, limit: int = 100) -> list[dict[str, Any]]:
        return [
            self._strip_mongo(doc)
            for doc in self._col(table).find({}, {"_id": 0}).limit(limit)
        ]

    def get_row(self, table: str, row_id: int) -> dict[str, Any] | None:
        return self._find_by(table, "id", row_id)

    def insert_row(self, table: str, payload: dict[str, Any]) -> dict[str, Any]:
        row = {"id": self._next_id(table), **payload}
        self._col(table).insert_one({**row})
        return row

    def update_row(self, table: str, row_id: int, payload: dict[str, Any]) -> dict[str, Any] | None:
        result = self._col(table).find_one_and_update(
            {"id": row_id},
            {"$set": payload},
            return_document=True,
            projection={"_id": 0},
        )
        return result

    def delete_row(self, table: str, row_id: int) -> dict[str, Any] | None:
        doc = self._col(table).find_one({"id": row_id}, {"_id": 0})
        if doc:
            self._col(table).delete_one({"id": row_id})
        return doc

    def clear_table(self, table: str) -> int:
        count = self._col(table).count_documents({})
        self._col(table).delete_many({})
        self._db[_COUNTERS_COLLECTION].delete_one({"_id": table})
        return count

    def update_rows_by_field(self, table: str, field: str, value: Any, payload: dict[str, Any]) -> int:
        result = self._col(table).update_many({field: value}, {"$set": payload})
        return result.modified_count

    # ------------------------------------------------------------------
    # Bootstrap (same logic as DatabaseService.bootstrap_from_excels)
    # ------------------------------------------------------------------

    def bootstrap_from_excels(self) -> dict[str, int]:
        self.init_db()

        hackaton_path = self.raw_dir / "Hackaton.xlsx"
        horarios_path = self.raw_dir / "Horarios Entrega.XLSX"
        zm040_path = self.raw_dir / "ZM040.XLSX"

        detail_df = pd.read_excel(hackaton_path, sheet_name="Detalle entrega")
        address_df = pd.read_excel(hackaton_path, sheet_name="Direcciones")
        zones_df = pd.read_excel(hackaton_path, sheet_name="ZONAS")
        locations_df = pd.read_excel(hackaton_path, sheet_name="Materiales zubic")
        schedule_df = pd.read_excel(horarios_path)
        dimensions_df = pd.read_excel(zm040_path)

        self._bootstrap_customers(address_df, zones_df)
        self._bootstrap_drivers_routes_transports(detail_df)
        self._bootstrap_materials(detail_df, locations_df, dimensions_df)
        self._bootstrap_time_windows(schedule_df)
        self._bootstrap_delivery_stops_and_lines(detail_df)
        return self.list_tables()

    # ------------------------------------------------------------------
    # Seed helpers
    # ------------------------------------------------------------------

    def _seed_material_types(self) -> None:
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
            self._upsert("material_types", "code", {"code": code, "name": name, "description": description})

    def _seed_default_warehouse(self) -> None:
        self._upsert(
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

    def _bootstrap_customers(self, address_df: pd.DataFrame, zones_df: pd.DataFrame) -> None:
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

    def _bootstrap_drivers_routes_transports(self, detail_df: pd.DataFrame) -> None:
        for _, row in (
            detail_df[["Repartidor", "Destinatario mcía.", "Ruta", "Transporte", "FECHA"]]
            .drop_duplicates(subset=["Transporte"])
            .iterrows()
        ):
            driver_code = _clean_id(row["Repartidor"])
            route_code = _clean_text(row["Ruta"])
            transport_code = _clean_id(row["Transporte"])
            transport_date = pd.to_datetime(row["FECHA"], dayfirst=True, errors="coerce")
            driver = self._upsert("drivers", "code", {"code": driver_code, "name": _clean_text(row["Destinatario mcía."])})
            route = self._upsert("routes", "code", {"code": route_code, "name": route_code, "zone_code": None})
            self._upsert(
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
        detail_df: pd.DataFrame,
        locations_df: pd.DataFrame,
        dimensions_df: pd.DataFrame,
    ) -> None:
        warehouse = self._find_by("warehouses", "code", "D131")
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
        material_type_map = {row["code"]: row["id"] for row in self.list_rows("material_types", limit=100)}
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
                existing = self._col("material_dimensions").find_one(
                    {"material_id": material_row["id"], "unit": unit}, {"_id": 0}
                )
                payload = {
                    "material_id": material_row["id"],
                    "unit": unit,
                    "counter": int(dim_row["Contador"]) if pd.notna(dim_row["Contador"]) else None,
                    "length_cm": self._normalize_length(dim_row["Longitud"], dim_row["Unidad dimensión"]),
                    "width_cm": self._normalize_length(dim_row["Ancho"], dim_row.get("Unidad dimensión.1", dim_row["Unidad dimensión"])),
                    "height_cm": self._normalize_length(dim_row["Altura"], dim_row.get("Unidad dimensión.2", dim_row["Unidad dimensión"])),
                    "volume_l": float(dim_row["Volumen"]) if pd.notna(dim_row["Volumen"]) and dim_row["Volumen"] else None,
                    "weight_gross_kg": self._normalize_weight(dim_row["Peso bruto"], dim_row["Un"]),
                    "weight_net_kg": self._normalize_weight(dim_row["Peso neto"], dim_row.get("Un.2", dim_row["Un"])),
                }
                if existing is None:
                    self._col("material_dimensions").insert_one({"id": self._next_id("material_dimensions"), **payload})
                else:
                    self._col("material_dimensions").update_one(
                        {"material_id": material_row["id"], "unit": unit}, {"$set": payload}
                    )
                hierarchy_code = _clean_text(dim_row.get("Jquía.productos"))
                if hierarchy_code:
                    self._col("materials").update_one({"id": material_row["id"]}, {"$set": {"product_hierarchy_code": hierarchy_code}})

    def _bootstrap_time_windows(self, schedule_df: pd.DataFrame) -> None:
        customer_map = {row["code"]: row["id"] for row in self.list_rows("customers", limit=10000)}
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
            existing = self._col("customer_time_windows").find_one(
                {
                    "customer_id": payload["customer_id"],
                    "weekday": payload["weekday"],
                    "shift": payload["shift"],
                    "open_time": payload["open_time"],
                    "close_time": payload["close_time"],
                },
                {"_id": 0},
            )
            if existing is None:
                self._col("customer_time_windows").insert_one(
                    {"id": self._next_id("customer_time_windows"), **payload}
                )
            else:
                self._col("customer_time_windows").update_one(
                    {"id": existing["id"]}, {"$set": payload}
                )

    def _bootstrap_delivery_stops_and_lines(self, detail_df: pd.DataFrame) -> None:
        customer_map = {row["code"]: row["id"] for row in self.list_rows("customers", limit=10000)}
        transport_map = {row["code"]: row["id"] for row in self.list_rows("transports", limit=20000)}
        material_map = {row["code"]: row["id"] for row in self.list_rows("materials", limit=10000)}
        detail_df = detail_df.copy()
        detail_df["_source_order"] = range(len(detail_df))
        for transport_code, transport_rows in detail_df.groupby("Transporte", sort=False):
            transport_id = transport_map.get(_clean_id(transport_code))
            if transport_id is None:
                continue
            ordered_rows = transport_rows.sort_values("_source_order")
            for sequence, (delivery_code, stop_rows) in enumerate(
                ordered_rows.groupby("Entrega", sort=False), start=1
            ):
                first = stop_rows.iloc[0]
                customer_id = customer_map.get(_clean_id(first["Destinatario mcía..1"]))
                if customer_id is None:
                    continue
                stop_row = self._upsert(
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
                    existing = self._col("delivery_lines").find_one(
                        {
                            "delivery_stop_id": payload["delivery_stop_id"],
                            "material_id": payload["material_id"],
                            "sales_unit": payload["sales_unit"],
                        },
                        {"_id": 0},
                    )
                    if existing is None:
                        self._col("delivery_lines").insert_one(
                            {"id": self._next_id("delivery_lines"), **payload}
                        )
                    else:
                        self._col("delivery_lines").update_one({"id": existing["id"]}, {"$set": {"quantity": payload["quantity"]}})

    # ------------------------------------------------------------------
    # Unit conversion helpers (identical to DatabaseService)
    # ------------------------------------------------------------------

    def _normalize_length(self, value: Any, unit: Any) -> float | None:
        if pd.isna(value):
            return None
        raw = float(value)
        if raw <= 0:
            return None
        u = _clean_text(unit).upper()
        if u == "MM":
            return raw / 10
        if u == "M":
            return raw * 100
        return raw

    def _normalize_weight(self, value: Any, unit: Any) -> float | None:
        if pd.isna(value):
            return None
        raw = float(value)
        if raw <= 0:
            return None
        u = _clean_text(unit).upper()
        if u in {"G", "GR"}:
            return raw / 1000
        return raw

    def _normalize_time(self, value: Any) -> str | None:
        if pd.isna(value):
            return None
        parsed = pd.to_datetime(str(value), errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.time().replace(microsecond=0).isoformat()
