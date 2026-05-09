from __future__ import annotations

import io
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from main import app
from routers import data as data_router
from services.database import DatabaseService
from services.order_import import OrderImporter


def _seeded_service(tmp_path: Path) -> tuple[DatabaseService, str, str]:
    service = DatabaseService(db_path=tmp_path / "app_db.json")
    service.init_db()
    db = service.load()
    customer = service.stage_insert(db, "customers", {"name": "JACINT MAS CORNET", "city": "VIC"})
    material = service.stage_insert(
        db,
        "materials",
        {"description": "ESTRELLA DAMM 1/3 RET. PP", "base_unit": "CAJ", "is_returnable": True},
    )
    service.save(db)
    return service, customer["id"], material["id"]


def test_importer_inserts_orders_only_for_known_ids(tmp_path: Path) -> None:
    service, customer_id, material_id = _seeded_service(tmp_path)
    importer = OrderImporter(service=service)
    csv_text = (
        "customer_id;material_id;quantity;sales_unit\n"
        f"{customer_id};{material_id};3;CAJ\n"
        f"{customer_id};00000000-0000-0000-0000-000000000000;2;UN\n"
        f"00000000-0000-0000-0000-000000000001;{material_id};1;CAJ\n"
        f"{customer_id};{material_id};not-a-number;CAJ\n"
        f"{customer_id};{material_id};-1;CAJ\n"
    )

    summary = importer.import_csv(csv_text.encode("utf-8"), due_date=date(2026, 5, 9))

    assert summary.received == 5
    assert summary.inserted == 1
    assert summary.skipped == 4
    assert summary.unknown_customers == ["00000000-0000-0000-0000-000000000001"]
    assert summary.unknown_materials == ["00000000-0000-0000-0000-000000000000"]
    reasons = {error.reason for error in summary.errors}
    assert reasons == {
        "unknown_customer",
        "unknown_material",
        "invalid_quantity",
        "non_positive_quantity",
    }

    db = service.load()
    assert len(db["tables"]["customers"]) == 1
    assert len(db["tables"]["materials"]) == 1
    orders = db["tables"]["orders"]
    assert len(orders) == 1
    assert orders[0]["customer_id"] == customer_id
    assert orders[0]["material_id"] == material_id
    assert orders[0]["sales_unit"] == "CAJ"
    assert orders[0]["due_date"] == "2026-05-09"
    assert orders[0]["delivered_flag"] is False
    assert orders[0]["imported_via_csv"] is True


def test_importer_rejects_csv_missing_required_columns(tmp_path: Path) -> None:
    service, _, _ = _seeded_service(tmp_path)
    importer = OrderImporter(service=service)

    try:
        importer.import_csv("foo;bar\n1;2\n")
    except ValueError as exc:
        assert "customer_id" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_orders_import_endpoint_returns_summary(tmp_path: Path) -> None:
    service, customer_id, material_id = _seeded_service(tmp_path)
    original_importer = data_router.order_importer
    data_router.order_importer = OrderImporter(service=service)
    client = TestClient(app)

    csv_bytes = (
        "customer_id;material_id;quantity;sales_unit\n"
        f"{customer_id};{material_id};4;CAJ\n"
        f"00000000-0000-0000-0000-000000000099;{material_id};1;UN\n"
    ).encode("utf-8")

    try:
        response = client.post(
            "/api/v1/data/orders/import",
            files={"file": ("orders.csv", io.BytesIO(csv_bytes), "text/csv")},
            data={"due_date": "2026-05-09"},
        )
    finally:
        data_router.order_importer = original_importer

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["received"] == 2
    assert payload["inserted"] == 1
    assert payload["skipped"] == 1
    assert payload["unknown_customers"] == ["00000000-0000-0000-0000-000000000099"]
    assert payload["unknown_materials"] == []


def test_clear_imported_removes_only_marked_orders(tmp_path: Path) -> None:
    service, customer_id, material_id = _seeded_service(tmp_path)
    importer = OrderImporter(service=service)

    db = service.load()
    seeded_order = service.stage_insert(
        db,
        "orders",
        {
            "customer_id": customer_id,
            "material_id": material_id,
            "due_date": "2026-01-30",
            "quantity": 1.0,
            "sales_unit": "CAJ",
            "delivered_flag": False,
        },
    )
    stop = service.stage_insert(
        db,
        "delivery_stops",
        {"transport_id": None, "customer_id": customer_id, "sequence": 1},
    )
    service.stage_insert(
        db,
        "delivery_lines",
        {"delivery_stop_id": stop["id"], "order_id": seeded_order["id"]},
    )
    service.save(db)

    csv_text = (
        "customer_id;material_id;quantity;sales_unit\n"
        f"{customer_id};{material_id};3;CAJ\n"
        f"{customer_id};{material_id};5;CAJ\n"
    )
    importer.import_csv(csv_text)

    assert len(service.load()["tables"]["orders"]) == 3

    summary = importer.clear_imported()

    assert summary.deleted_orders == 2
    assert summary.deleted_delivery_lines == 0

    final_db = service.load()
    remaining_orders = final_db["tables"]["orders"]
    assert len(remaining_orders) == 1
    assert remaining_orders[0]["id"] == seeded_order["id"]
    assert remaining_orders[0].get("imported_via_csv") is None
    assert len(final_db["tables"]["delivery_lines"]) == 1


def test_clear_imported_endpoint_returns_counts(tmp_path: Path) -> None:
    service, customer_id, material_id = _seeded_service(tmp_path)
    original_importer = data_router.order_importer
    data_router.order_importer = OrderImporter(service=service)
    client = TestClient(app)

    csv_bytes = (
        "customer_id;material_id;quantity;sales_unit\n"
        f"{customer_id};{material_id};2;CAJ\n"
        f"{customer_id};{material_id};4;CAJ\n"
    ).encode("utf-8")

    try:
        client.post(
            "/api/v1/data/orders/import",
            files={"file": ("orders.csv", io.BytesIO(csv_bytes), "text/csv")},
        )
        response = client.delete("/api/v1/data/orders/imported")
    finally:
        data_router.order_importer = original_importer

    assert response.status_code == 200
    payload = response.json()
    assert payload == {"status": "ok", "deleted_orders": 2, "deleted_delivery_lines": 0}
    assert service.load()["tables"]["orders"] == []


def test_clear_imported_is_idempotent_when_nothing_to_delete(tmp_path: Path) -> None:
    service, _, _ = _seeded_service(tmp_path)
    importer = OrderImporter(service=service)

    summary = importer.clear_imported()

    assert summary.deleted_orders == 0
    assert summary.deleted_delivery_lines == 0


def test_orders_import_endpoint_rejects_empty_file(tmp_path: Path) -> None:
    service, _, _ = _seeded_service(tmp_path)
    original_importer = data_router.order_importer
    data_router.order_importer = OrderImporter(service=service)
    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/data/orders/import",
            files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
        )
    finally:
        data_router.order_importer = original_importer

    assert response.status_code == 400
    assert response.json()["detail"] == "Empty CSV upload"
