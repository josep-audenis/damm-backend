from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from main import app
from routers import db as db_router
from services.database import DatabaseService


def test_dynamic_db_api_reads_schema_and_writes_rows(tmp_path: Path) -> None:
    service = DatabaseService(db_path=tmp_path / "api_db.json")
    original_service = db_router.db_service
    db_router.db_service = service
    client = TestClient(app)

    try:
        create_response = client.post(
            "/api/v1/db/experiments",
            json={"name": "api-test", "enabled": True},
        )
        assert create_response.status_code == 201
        assert create_response.json() == {"id": 1, "name": "api-test", "enabled": True}

        update_response = client.patch("/api/v1/db/experiments/1", json={"score": 7})
        assert update_response.status_code == 200
        assert update_response.json()["score"] == 7

        schema_response = client.get("/api/v1/db/experiments/schema")
        assert schema_response.status_code == 200
        assert schema_response.json() == {
            "enabled": ["bool"],
            "id": ["int"],
            "name": ["str"],
            "score": ["int"],
        }

        list_response = client.get("/api/v1/db/experiments")
        assert list_response.status_code == 200
        assert list_response.json() == [update_response.json()]
    finally:
        db_router.db_service = original_service


def test_dynamic_db_api_rejects_client_supplied_ids(tmp_path: Path) -> None:
    service = DatabaseService(db_path=tmp_path / "api_db.json")
    original_service = db_router.db_service
    db_router.db_service = service
    client = TestClient(app)

    try:
        response = client.post("/api/v1/db/experiments", json={"id": 99, "name": "bad"})
        assert response.status_code == 400
        assert response.json()["detail"] == "Payload must not include id"
    finally:
        db_router.db_service = original_service


def test_dynamic_db_api_clears_table(tmp_path: Path) -> None:
    service = DatabaseService(db_path=tmp_path / "api_db.json")
    original_service = db_router.db_service
    db_router.db_service = service
    client = TestClient(app)

    try:
        client.post("/api/v1/db/experiments", json={"name": "first"})
        client.post("/api/v1/db/experiments", json={"name": "second"})

        response = client.delete("/api/v1/db/experiments")

        assert response.status_code == 200
        assert response.json() == {"table": "experiments", "deleted": 2}
        assert client.get("/api/v1/db/experiments").json() == []
        assert client.get("/api/v1/db/tables").json()["experiments"] == 0
    finally:
        db_router.db_service = original_service
