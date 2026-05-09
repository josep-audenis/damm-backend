from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from services.database import DatabaseService, db_service


CSV_REQUIRED_COLUMNS = {"customer_id", "material_id", "quantity", "sales_unit"}
CSV_KNOWN_COLUMNS = CSV_REQUIRED_COLUMNS | {"due_date"}


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


@dataclass
class ClearImportedSummary:
    deleted_orders: int = 0
    deleted_delivery_lines: int = 0


IMPORT_MARKER_FIELD = "imported_via_csv"


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

    The CSV uses the same column names as the `orders` JSON DB schema:

        customer_id;material_id;quantity;sales_unit[;due_date]

    `customer_id` and `material_id` must be UUIDs that already exist in the
    `customers` / `materials` tables — the importer never creates new rows in
    those tables. Rows whose IDs are unknown are skipped and reported via
    `unknown_customers` / `unknown_materials`. Every inserted order is tagged
    with `imported_via_csv: true` so it can be cleaned up later via
    :meth:`clear_imported`.
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
        customer_ids = {row["id"] for row in db["tables"].get("customers", []) if row.get("id")}
        material_ids = {row["id"] for row in db["tables"].get("materials", []) if row.get("id")}
        target_due_date = (due_date or date.today()).isoformat()

        summary = ImportSummary()
        unknown_customers: set[str] = set()
        unknown_materials: set[str] = set()

        for line_no, raw_row in enumerate(reader, start=2):
            row = {(key or "").strip().lower(): (value or "") for key, value in raw_row.items()}
            summary.received += 1

            customer_id = row.get("customer_id", "").strip()
            material_id = row.get("material_id", "").strip()
            sales_unit = row.get("sales_unit", "").strip().upper()
            quantity = _coerce_quantity(row.get("quantity", ""))
            due = _coerce_due_date(row.get("due_date"), date.fromisoformat(target_due_date))

            if not customer_id or not material_id or not sales_unit:
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
            if customer_id not in customer_ids:
                summary.skipped += 1
                unknown_customers.add(customer_id)
                summary.errors.append(
                    ImportRowError(row=line_no, reason="unknown_customer", raw=row)
                )
                continue
            if material_id not in material_ids:
                summary.skipped += 1
                unknown_materials.add(material_id)
                summary.errors.append(
                    ImportRowError(row=line_no, reason="unknown_material", raw=row)
                )
                continue

            self.service.stage_insert(
                db,
                "orders",
                {
                    "customer_id": customer_id,
                    "due_date": due,
                    "material_id": material_id,
                    "quantity": quantity,
                    "sales_unit": sales_unit,
                    "delivered_flag": False,
                    IMPORT_MARKER_FIELD: True,
                },
            )
            summary.inserted += 1

        if summary.inserted:
            self.service.save(db)
        summary.unknown_customers = sorted(unknown_customers)
        summary.unknown_materials = sorted(unknown_materials)
        return summary

    def clear_imported(self) -> ClearImportedSummary:
        """Delete every order created through `import_csv` and any delivery
        lines pointing at them. Existing seeded orders (without the marker)
        are left untouched.
        """
        db = self.service.load()
        orders = db["tables"].get("orders", [])
        imported_ids = {row["id"] for row in orders if row.get(IMPORT_MARKER_FIELD)}
        if not imported_ids:
            return ClearImportedSummary()

        kept_orders = [row for row in orders if row["id"] not in imported_ids]
        deleted_orders = len(orders) - len(kept_orders)
        db["tables"]["orders"] = kept_orders

        delivery_lines = db["tables"].get("delivery_lines", [])
        kept_lines = [row for row in delivery_lines if row.get("order_id") not in imported_ids]
        deleted_lines = len(delivery_lines) - len(kept_lines)
        if deleted_lines:
            db["tables"]["delivery_lines"] = kept_lines

        self.service.save(db)
        return ClearImportedSummary(
            deleted_orders=deleted_orders,
            deleted_delivery_lines=deleted_lines,
        )

    def _decode(self, content: bytes | str) -> str:
        if isinstance(content, str):
            return content
        try:
            return content.decode("utf-8-sig")
        except UnicodeDecodeError:
            return content.decode("latin-1", errors="replace")


order_importer = OrderImporter()
