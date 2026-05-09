from __future__ import annotations

import io
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from main import app
from routers import data as data_router
from services.database import DatabaseService
from services.order_import import OrderImporter


def _seeded_service(tmp_path: Path) -> DatabaseService:
    service = DatabaseService(db_path=tmp_path / "app_db.json")
    service.init_db()
    db = service.load()
    service.stage_insert(db, "customers", {"name": "JACINT MAS CORNET", "city": "VIC"})
    service.stage_insert(
        db,
        "materials",
        {"description": "ESTRELLA DAMM 1/3 RET. PP", "base_unit": "CAJ", "is_returnable": True},
    )
    service.save(db)
    return service


def test_importer_inserts_orders_only_for_known_customers_and_materials(tmp_path: Path) -> None:
    service = _seeded_service(tmp_path)
    importer = OrderImporter(service=service)
    csv_text = (
        "customer_name;material_code;material_name;qty;unit\n"
        "JACINT MAS CORNET;ED13;ESTRELLA DAMM 1/3 RET. PP;3;CAJ\n"
        "JACINT MAS CORNET;0XX0001;NEW MATERIAL X;2;UN\n"
        "UNKNOWN PERSON;ED13;ESTRELLA DAMM 1/3 RET. PP;1;CAJ\n"
        "JACINT MAS CORNET;ED13;ESTRELLA DAMM 1/3 RET. PP;not-a-number;CAJ\n"
    )

    summary = importer.import_csv(csv_text.encode("utf-8"), due_date=date(2026, 5, 9))

    assert summary.received == 4
    assert summary.inserted == 1
    assert summary.skipped == 3
    assert summary.unknown_customers == ["UNKNOWN PERSON"]
    assert summary.unknown_materials == ["NEW MATERIAL X"]

    reasons = {error.reason for error in summary.errors}
    assert reasons == {"unknown_customer", "unknown_material", "invalid_quantity"}

    db = service.load()
    assert len(db["tables"]["customers"]) == 1
    assert len(db["tables"]["materials"]) == 1
    orders = db["tables"]["orders"]
    assert len(orders) == 1
    assert orders[0]["sales_unit"] == "CAJ"
    assert orders[0]["due_date"] == "2026-05-09"
    assert orders[0]["delivered_flag"] is False


def test_importer_rejects_csv_missing_required_columns(tmp_path: Path) -> None:
    service = _seeded_service(tmp_path)
    importer = OrderImporter(service=service)

    try:
        importer.import_csv("foo;bar\n1;2\n")
    except ValueError as exc:
        assert "customer_name" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_orders_import_endpoint_returns_summary(tmp_path: Path) -> None:
    service = _seeded_service(tmp_path)
    original_importer = data_router.order_importer
    data_router.order_importer = OrderImporter(service=service)
    client = TestClient(app)

    csv_bytes = (
        "customer_name;material_code;material_name;qty;unit\n"
        "JACINT MAS CORNET;ED13;ESTRELLA DAMM 1/3 RET. PP;4;CAJ\n"
        "MISSING ONE;ZZZ;Z PRODUCT;1;UN\n"
        "JACINT MAS CORNET;NEW;NEW PRODUCT;2;UN\n"
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
    assert payload["received"] == 3
    assert payload["inserted"] == 1
    assert payload["skipped"] == 2
    assert payload["unknown_customers"] == ["MISSING ONE"]
    assert payload["unknown_materials"] == ["NEW PRODUCT"]
    assert "customers_created" not in payload
    assert "materials_created" not in payload


def test_orders_import_endpoint_rejects_empty_file(tmp_path: Path) -> None:
    service = _seeded_service(tmp_path)
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
