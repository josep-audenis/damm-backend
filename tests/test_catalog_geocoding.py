from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi.testclient import TestClient

from main import app
from routers import catalog as catalog_router


@dataclass(frozen=True)
class FakeCoordinates:
    lat: float
    lng: float


class FakeDatabaseService:
    def __init__(self) -> None:
        self.customer = {
            "id": "customer-uuid",
            "name": "BAR TEST",
            "address": "CARRER TEST 1",
            "postal_code": "08100",
            "city": "MOLLET DEL VALLÈS",
            "lat": None,
            "lng": None,
        }
        self.updated_row_id: str | None = None
        self.updated_stops: tuple[str, str, dict[str, float]] | None = None

    def list_rows(self, table: str, limit: int = 100) -> list[dict[str, Any]]:
        assert table == "customers"
        assert limit == 1000000
        return [self.customer]

    def update_row(self, table: str, row_id: str, payload: dict[str, float]) -> dict[str, Any]:
        assert table == "customers"
        self.updated_row_id = row_id
        self.customer.update(payload)
        return self.customer

    def update_rows_by_field(self, table: str, field: str, value: str, payload: dict[str, float]) -> int:
        self.updated_stops = (table, field, payload)
        assert value == "customer-uuid"
        return 1


def test_geocode_missing_customers_uses_uuid_ids_and_exact_query(monkeypatch: Any) -> None:
    service = FakeDatabaseService()
    calls: list[tuple[dict[str, Any], bool]] = []

    async def fake_geocode_location(row: dict[str, Any], use_fallbacks: bool = True) -> FakeCoordinates:
        calls.append((row, use_fallbacks))
        return FakeCoordinates(lat=41.5, lng=2.2)

    monkeypatch.setattr(catalog_router, "db_service", service)
    monkeypatch.setattr(catalog_router, "geocode_location", fake_geocode_location)

    response = TestClient(app).post("/api/v1/catalog/customers/geocode-missing")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "processed": 1, "updated": 1, "failed": 0}
    assert service.updated_row_id == "customer-uuid"
    assert service.updated_stops == ("delivery_stops", "customer_id", {"lat": 41.5, "lng": 2.2})
    assert calls == [(service.customer, False)]
