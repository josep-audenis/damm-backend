from __future__ import annotations

import json
import uuid
from pathlib import Path

import pandas as pd

from services.database import DatabaseService


def _assert_uuid(value: object) -> str:
    assert isinstance(value, str)
    assert str(uuid.UUID(value)) == value
    return value


def test_database_service_migrates_removed_tables_fields_ids_and_strings(tmp_path: Path) -> None:
    db_path = tmp_path / "app_db.json"
    db_path.write_text(
        json.dumps(
            {
                "meta": {},
                "seq": {
                    "customer_time_windows": 1,
                    "customers": 1,
                    "drivers": 1,
                    "material_types": 1,
                    "materials": 1,
                    "source_documents": 1,
                    "source_document_lines": 0,
                    "transports": 1,
                    "trucks": 1,
                    "warehouses": 1,
                    "warehouse_locations": 1,
                    "delivery_stops": 1,
                    "delivery_lines": 1,
                },
                "tables": {
                    "warehouses": [
                        {
                            "id": 1,
                            "code": "D131",
                            "name": "DDI Mollet",
                            "address": "calle del moli 1",
                            "storage_center_code": "D131",
                            "created_at": "2026-05-09T00:00:00+00:00",
                        }
                    ],
                    "customer_time_windows": [
                        {
                            "id": 1,
                            "customer_id": 1,
                            "weekday": 1,
                            "shift": 1,
                            "open_time": "10:00:00",
                            "close_time": "11:00:00",
                            "is_closed": False,
                        }
                    ],
                    "customers": [
                        {
                            "id": 1,
                            "code": "9100000000",
                            "name": "Customer",
                            "address": "avda diagonal 12",
                            "payment_condition": None,
                            "service_notes": None,
                        }
                    ],
                    "drivers": [{"id": 1, "code": "850000", "name": "Driver"}],
                    "material_types": [{"id": 1, "code": "beer_bottle", "name": "Beer Bottle"}],
                    "materials": [
                        {
                            "id": 1,
                            "code": "ED13",
                            "description": "Beer",
                            "manufacturer": "5001",
                            "manufacturer_code": "S.A. DAMM",
                            "product_hierarchy_code": "H",
                        }
                    ],
                    "source_documents": [{"id": 1}],
                    "source_document_lines": [],
                    "transports": [
                        {
                            "id": 1,
                            "code": "11420379",
                            "transport_date": "2026-01-30",
                            "load_number": None,
                            "trip_number": None,
                        }
                    ],
                    "trucks": [
                        {
                            "id": 1,
                            "code": "TRUCK-1",
                            "plate": "test1234",
                            "truck_type": "8pal",
                            "capacity_pallets": 8,
                            "warehouse_id": 1,
                            "active": 1,
                        }
                    ],
                    "warehouse_locations": [{"id": 1}],
                    "delivery_stops": [
                        {
                            "id": 1,
                            "delivery_code": "827937019",
                            "transport_id": 1,
                            "customer_id": 1,
                            "sequence": 1,
                            "address_snapshot": "Street 1",
                            "postal_code_snapshot": "08100",
                            "city_snapshot": "Mollet",
                        }
                    ],
                    "delivery_lines": [
                        {
                            "id": 1,
                            "delivery_stop_id": 1,
                            "material_id": 1,
                            "quantity": 2.0,
                            "sales_unit": "CAJ",
                            "warehouse_location_code": None,
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    service = DatabaseService(db_path=db_path)
    service.init_db()
    migrated = json.loads(db_path.read_text(encoding="utf-8"))

    assert "seq" not in migrated
    assert "source_documents" not in migrated["tables"]
    assert "source_document_lines" not in migrated["tables"]
    assert "warehouse_locations" not in migrated["tables"]

    warehouse = migrated["tables"]["warehouses"][0]
    customer = migrated["tables"]["customers"][0]
    time_window = migrated["tables"]["customer_time_windows"][0]
    driver = migrated["tables"]["drivers"][0]
    material_type = migrated["tables"]["material_types"][0]
    material = migrated["tables"]["materials"][0]
    transport = migrated["tables"]["transports"][0]
    truck = migrated["tables"]["trucks"][0]
    stop = migrated["tables"]["delivery_stops"][0]
    order = migrated["tables"]["orders"][0]
    line = migrated["tables"]["delivery_lines"][0]

    for row in [warehouse, customer, time_window, driver, material_type, material, transport, truck, stop, order, line]:
        _assert_uuid(row["id"])

    assert warehouse["name"] == "DDI MOLLET"
    assert warehouse["address"] == "CARRER DEL MOLI 1"
    assert customer["name"] == "CUSTOMER"
    assert customer["address"] == "AVINGUDA DIAGONAL 12"
    assert driver == {"id": driver["id"], "name": "DRIVER"}
    assert material_type["name"] == "BEER BOTTLE"
    assert material_type["description"] == "RETURNABLE OR NON-RETURNABLE BOTTLED BEER"
    assert material == {"id": material["id"], "description": "BEER"}
    assert truck["plate"] == "TEST1234"

    assert time_window["customer_id"] == customer["id"]
    assert truck["warehouse_id"] == warehouse["id"]
    assert stop["transport_id"] == transport["id"]
    assert stop["customer_id"] == customer["id"]
    assert order["customer_id"] == customer["id"]
    assert order["material_id"] == material["id"]
    assert line["delivery_stop_id"] == stop["id"]
    assert line["order_id"] == order["id"]


def test_bootstrap_helpers_keep_source_keys_out_and_normalize_strings(tmp_path: Path) -> None:
    service = DatabaseService(db_path=tmp_path / "app_db.json")
    db = service._empty_db()

    customer_map = service._bootstrap_customers(
        db,
        pd.DataFrame(
            [
                {
                    "Cliente": "9100000000",
                    "Nombre 1": "Bar One",
                    "Nombre 2": "Bar One",
                    "Calle": "cr sant joan 1",
                    "CP": "08100",
                    "Población": "Mollet",
                },
                {
                    "Cliente": "9100000000",
                    "Nombre 1": "Duplicate",
                    "Nombre 2": "Duplicate",
                    "Calle": "Street 2",
                    "CP": "08100",
                    "Población": "Mollet",
                },
            ]
        ),
        pd.DataFrame(
            [
                {
                    "cliente zona": "9100000000",
                    "ZonaTransp": "DD13100002",
                    "Zona Entrega": "Mollet",
                }
            ]
        ),
    )

    customer_id = _assert_uuid(customer_map["9100000000"])
    assert db["tables"]["customers"] == [
        {
            "id": customer_id,
            "name": "BAR ONE",
            "name_2": "BAR ONE",
            "address": "CARRER SANT JOAN 1",
            "postal_code": "08100",
            "city": "MOLLET",
            "zone_code": "DD13100002",
            "zone_name": "MOLLET",
            "lat": None,
            "lng": None,
        }
    ]

    transport_map = service._bootstrap_drivers_routes_transports(
        db,
        pd.DataFrame(
            [
                {
                    "Repartidor": "850000",
                    "Destinatario mcía.": "Driver One",
                    "Ruta": "DR0001",
                    "Transporte": "11420379",
                    "FECHA": "30/01/2026",
                }
            ]
        ),
    )

    transport_id = _assert_uuid(transport_map["11420379"])
    driver_id = _assert_uuid(db["tables"]["drivers"][0]["id"])
    route_id = _assert_uuid(db["tables"]["routes"][0]["id"])
    assert db["tables"]["drivers"] == [{"id": driver_id, "name": "DRIVER ONE"}]
    assert db["tables"]["transports"] == [
        {
            "id": transport_id,
            "transport_date": "2026-01-30",
            "route_id": route_id,
            "driver_id": driver_id,
            "truck_id": None,
        }
    ]

    service._bootstrap_delivery_stops_and_lines(
        db,
        pd.DataFrame(
            [
                {
                    "Transporte": "11420379",
                    "Entrega": "827937019",
                    "FECHA": "30/01/2026",
                    "Destinatario mcía..1": "9100000000",
                    "Material": "ED13",
                    "Cantidad entrega": 2,
                    "Un.medida venta": "CAJ",
                }
            ]
        ),
        customer_map,
        transport_map,
        {"ED13": "material-uuid"},
    )

    order = db["tables"]["orders"][0]
    stop = db["tables"]["delivery_stops"][0]
    line = db["tables"]["delivery_lines"][0]
    _assert_uuid(order["id"])
    _assert_uuid(stop["id"])
    _assert_uuid(line["id"])

    assert order["customer_id"] == customer_id
    assert order["material_id"] == "material-uuid"
    assert order["sales_unit"] == "CAJ"
    assert stop["transport_id"] == transport_id
    assert stop["customer_id"] == customer_id
    assert line["delivery_stop_id"] == stop["id"]
    assert line["order_id"] == order["id"]


def test_insert_update_normalize_human_text_and_keep_codes(tmp_path: Path) -> None:
    service = DatabaseService(db_path=tmp_path / "app_db.json")

    row = service.insert_row(
        "customers",
        {
            "name": "bar two",
            "address": "plaza major",
            "city": "barcelona",
            "zone_code": "DD13100002",
        },
    )
    updated = service.update_row("customers", row["id"], {"address": "unknown road"})

    _assert_uuid(row["id"])
    assert updated is not None
    assert updated["name"] == "BAR TWO"
    assert updated["address"] == "UNKNOWN ROAD"
    assert updated["city"] == "BARCELONA"
    assert updated["zone_code"] == "DD13100002"
