from fastapi.testclient import TestClient

from main import app
from models.domain import DeliveryStop, ProductCategory, ProductLine, ProductUnit
from services.optimization import group_stops_by_customer


client = TestClient(app)


def test_group_stops_by_customer_merges_products_and_albarans() -> None:
    stops = [
        DeliveryStop(
            stop_id="A",
            sequence=1,
            customer_id="C1",
            customer_name="Client",
            address="Street 1",
            postal_code="08000",
            city="Mollet",
            products=[
                ProductLine(
                    material_code="ED13",
                    description="Beer",
                    quantity=2,
                    unit=ProductUnit.CAJ,
                    category=ProductCategory.BEER_BOTTLE,
                    is_returnable=True,
                )
            ],
            albaran_numbers=["A"],
        ),
        DeliveryStop(
            stop_id="B",
            sequence=2,
            customer_id="C1",
            customer_name="Client",
            address="Street 1",
            postal_code="08000",
            city="Mollet",
            products=[
                ProductLine(
                    material_code="KAS",
                    description="Soft drink",
                    quantity=3,
                    unit=ProductUnit.CAJ,
                    category=ProductCategory.SOFT_DRINK,
                    is_returnable=False,
                )
            ],
            albaran_numbers=["B"],
        ),
    ]

    grouped = group_stops_by_customer(stops)

    assert len(grouped) == 1
    assert grouped[0].stop_id == "A+B"
    assert [product.material_code for product in grouped[0].products] == ["ED13", "KAS"]
    assert grouped[0].albaran_numbers == ["A", "B"]


def test_optimize_preview_uses_real_transport_and_groups_client_orders() -> None:
    response = client.post(
        "/api/v1/optimize/full/preview",
        json={"transport_id": "11515121", "truck_type": "6pal", "solver_time_limit_s": 5},
    )

    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["status"] == "done"
    assert payload["route"]["transport_id"] == "11515121"
    assert payload["route"]["total_stops"] <= 32
    assert "orders grouped by customer" in payload["route"]["explanation"]
    assert payload["load"]["pallet_slots_total"] == 6
    assert payload["load"]["pick_list"]


def test_optimize_preview_unknown_transport_returns_404() -> None:
    response = client.post(
        "/api/v1/optimize/full/preview",
        json={"transport_id": "does-not-exist", "truck_type": "6pal"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Transport not found"
