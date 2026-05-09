from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from services.database import DatabaseService, db_service


CSV_REQUIRED_COLUMNS = {"customer_name", "qty", "unit"}
CSV_KNOWN_COLUMNS = {
    "customer_name",
    "material_code",
    "material_name",
    "qty",
    "quantity",
    "unit",
    "sales_unit",
    "due_date",
}


@dataclass
class ImportRowError:
    row: int
    reason: str
    raw: dict[str, str] = field(default_factory=dict)


@dataclass
class ImportSummary:
    received: int = 0
    inserted: int = 0
    skipped: int = 0
    errors: list[ImportRowError] = field(default_factory=list)
    unknown_customers: list[str] = field(default_factory=list)
    unknown_materials: list[str] = field(default_factory=list)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text.upper()


def _detect_delimiter(sample: str) -> str:
    head = sample.splitlines()[0] if sample else ""
    return ";" if head.count(";") > head.count(",") else ","


def _coerce_quantity(value: str) -> float | None:
    text = (value or "").strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _coerce_due_date(value: str | None, fallback: date) -> str:
    if not value:
        return fallback.isoformat()
    try:
        return date.fromisoformat(value.strip()).isoformat()
    except ValueError:
        return fallback.isoformat()


class OrderImporter:
    """Parses an orders CSV and inserts rows into the `orders` table.

    Strict mode: rows whose customer or material is not already in the DB are
    skipped and reported. The importer never creates new `customers` or
    `materials` rows. Customer matching is by uppercase `name`; material
    matching is by uppercase `description` (with `material_name` preferred over
    `material_code` since the JSON DB does not store source SKU codes).
    """

    def __init__(self, service: DatabaseService = db_service) -> None:
        self.service = service

    def import_csv(
        self,
        content: bytes | str,
        due_date: date | None = None,
    ) -> ImportSummary:
        text = self._decode(content)
        if not text.strip():
            return ImportSummary()

        delimiter = _detect_delimiter(text[:2048])
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        if reader.fieldnames is None:
            return ImportSummary()

        headers = {(name or "").strip().lower() for name in reader.fieldnames}
        missing = CSV_REQUIRED_COLUMNS - headers
        if missing:
            raise ValueError(f"Missing required CSV columns: {sorted(missing)}")

        db = self.service.load()
        customers_index = self._index_customers(db)
        materials_index = self._index_materials(db)
        target_due_date = (due_date or date.today()).isoformat()

        summary = ImportSummary()
        unknown_customers: set[str] = set()
        unknown_materials: set[str] = set()

        for line_no, raw_row in enumerate(reader, start=2):
            row = {(key or "").strip().lower(): (value or "") for key, value in raw_row.items()}
            summary.received += 1

            customer_name = row.get("customer_name", "").strip()
            material_code = row.get("material_code", "").strip()
            material_name = row.get("material_name", "").strip()
            unit = (row.get("unit") or row.get("sales_unit") or "").strip().upper()
            qty_raw = row.get("qty") or row.get("quantity") or ""
            quantity = _coerce_quantity(qty_raw)
            due = _coerce_due_date(row.get("due_date"), date.fromisoformat(target_due_date))

            if not customer_name or not unit or not (material_code or material_name):
                summary.skipped += 1
                summary.errors.append(
                    ImportRowError(row=line_no, reason="missing_required_fields", raw=row)
                )
                continue
            if quantity is None:
                summary.skipped += 1
                summary.errors.append(
                    ImportRowError(row=line_no, reason="invalid_quantity", raw=row)
                )
                continue
            if quantity <= 0:
                summary.skipped += 1
                summary.errors.append(
                    ImportRowError(row=line_no, reason="non_positive_quantity", raw=row)
                )
                continue

            customer_key = _normalize_text(customer_name)
            customer = customers_index.get(customer_key)
            if customer is None:
                summary.skipped += 1
                unknown_customers.add(customer_key)
                summary.errors.append(
                    ImportRowError(row=line_no, reason="unknown_customer", raw=row)
                )
                continue

            material_key = _normalize_text(material_name) if material_name else None
            material = materials_index.get(material_key) if material_key else None
            if material is None:
                summary.skipped += 1
                unknown_materials.add(material_key or _normalize_text(material_code))
                summary.errors.append(
                    ImportRowError(row=line_no, reason="unknown_material", raw=row)
                )
                continue

            self.service.stage_insert(
                db,
                "orders",
                {
                    "customer_id": customer["id"],
                    "due_date": due,
                    "material_id": material["id"],
                    "quantity": quantity,
                    "sales_unit": unit,
                    "delivered_flag": False,
                },
            )
            summary.inserted += 1

        if summary.inserted:
            self.service.save(db)
        summary.unknown_customers = sorted(unknown_customers)
        summary.unknown_materials = sorted(unknown_materials)
        return summary

    def _decode(self, content: bytes | str) -> str:
        if isinstance(content, str):
            return content
        try:
            return content.decode("utf-8-sig")
        except UnicodeDecodeError:
            return content.decode("latin-1", errors="replace")

    def _index_customers(self, db: dict[str, Any]) -> dict[str, dict[str, Any]]:
        index: dict[str, dict[str, Any]] = {}
        for row in db["tables"].get("customers", []):
            key = _normalize_text(row.get("name"))
            if key and key not in index:
                index[key] = row
        return index

    def _index_materials(self, db: dict[str, Any]) -> dict[str, dict[str, Any]]:
        index: dict[str, dict[str, Any]] = {}
        for row in db["tables"].get("materials", []):
            key = _normalize_text(row.get("description"))
            if key and key not in index:
                index[key] = row
        return index


order_importer = OrderImporter()
