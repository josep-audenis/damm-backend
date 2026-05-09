from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from services.database import DatabaseService


def test_database_service_migrates_removed_tables_and_fields(tmp_path: Path) -> None:
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
                            "plate": "TEST1234",
                            "truck_type": "8pal",
                            "capacity_pallets": 8,
                            "warehouse_id": 1,
                            "active": 1,
                        }
                    ],
                    "warehouse_locations": [
                        {
                            "id": 1,
                            "code": "AA01A1",
                            "manufacturer": "5001",
                            "manufacturer_code": "S.A. DAMM",
                        }
                    ],
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

    assert "source_documents" not in migrated["tables"]
    assert "source_document_lines" not in migrated["tables"]
    assert "warehouse_locations" not in migrated["tables"]
    assert "warehouse_locations" not in migrated["seq"]
    assert migrated["tables"]["warehouses"][0] == {
        "id": 1,
        "name": "DDI Mollet",
        "address": None,
        "postal_code": None,
        "city": "Mollet del Vallès",
        "lat": None,
        "lng": None,
    }
    assert migrated["tables"]["customer_time_windows"][0] == {
        "id": 1,
        "customer_id": 1,
        "weekday": 1,
        "open_time": "10:00:00",
        "close_time": "11:00:00",
    }
    assert "code" not in migrated["tables"]["customers"][0]
    assert "code" not in migrated["tables"]["drivers"][0]
    assert "code" not in migrated["tables"]["material_types"][0]
    assert "code" not in migrated["tables"]["materials"][0]
    assert "manufacturer" not in migrated["tables"]["materials"][0]
    assert migrated["tables"]["transports"][0] == {
        "id": 1,
        "transport_date": "2026-01-30",
    }
    assert migrated["tables"]["trucks"][0] == {
        "id": 1,
        "plate": "TEST1234",
        "capacity_pallets": 8,
        "warehouse_id": 1,
    }
    assert migrated["tables"]["delivery_stops"][0] == {
        "id": 1,
        "transport_id": 1,
        "customer_id": 1,
        "sequence": 1,
        "lat": None,
        "lng": None,
    }
    assert migrated["tables"]["orders"][0] == {
        "id": 1,
        "customer_id": 1,
        "due_date": "2026-01-30",
        "material_id": 1,
        "quantity": 2.0,
        "sales_unit": "CAJ",
        "delivered_flag": False,
    }
    assert migrated["tables"]["delivery_lines"][0] == {
        "id": 1,
        "delivery_stop_id": 1,
        "order_id": 1,
    }


def test_bootstrap_helpers_keep_source_keys_out_of_stored_rows(tmp_path: Path) -> None:
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
                    "Calle": "Street 1",
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
                    "Zona Entrega": "MOLLET",
                }
            ]
        ),
    )

    assert customer_map == {"9100000000": 1}
    assert db["tables"]["customers"] == [
        {
            "id": 1,
            "name": "Bar One",
            "name_2": "Bar One",
            "address": "Street 1",
            "postal_code": "08100",
            "city": "Mollet",
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

    assert transport_map == {"11420379": 1}
    assert db["tables"]["drivers"] == [{"id": 1, "name": "Driver One"}]
    assert db["tables"]["transports"] == [
        {
            "id": 1,
            "transport_date": "2026-01-30",
            "route_id": 1,
            "driver_id": 1,
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
        {"ED13": 1},
    )

    assert db["tables"]["orders"] == [
        {
            "id": 1,
            "customer_id": 1,
            "due_date": "2026-01-30",
            "material_id": 1,
            "quantity": 2.0,
            "sales_unit": "CAJ",
            "delivered_flag": False,
        }
    ]
    assert db["tables"]["delivery_stops"] == [
        {
            "id": 1,
            "transport_id": 1,
            "customer_id": 1,
            "sequence": 1,
            "lat": None,
            "lng": None,
        }
    ]
    assert db["tables"]["delivery_lines"] == [
        {
            "id": 1,
            "delivery_stop_id": 1,
            "order_id": 1,
        }
    ]
