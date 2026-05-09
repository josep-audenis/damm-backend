from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_root_redirects_to_db_manager() -> None:
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/app/"


def test_db_manager_static_app_loads() -> None:
    response = client.get("/app/")

    assert response.status_code == 200
    assert "Damm DB Manager" in response.text
    assert "Clean table" in response.text


def test_db_manager_does_not_cap_visible_row_columns() -> None:
    response = client.get("/app/app.js")

    assert response.status_code == 200
    assert ".slice(0, 12)" not in response.text
