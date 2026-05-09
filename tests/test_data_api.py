from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_data_health_reports_real_counts() -> None:
    response = client.get("/api/v1/data/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data_loaded"] is True
    assert payload["customer_count"] == 200
    assert payload["transport_count"] > 0
    assert payload["geocoded_count"] > 0


def test_list_transports_returns_real_transport_summaries() -> None:
    response = client.get("/api/v1/data/transports")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) > 0
    assert all(item["transport_id"] for item in payload)
    assert any(item["stop_count"] > 0 for item in payload)


def test_transport_detail_uses_real_source_rows() -> None:
    transport_id = client.get("/api/v1/data/transports").json()[0]["transport_id"]
    response = client.get(f"/api/v1/data/transport/{transport_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["transport_id"] == transport_id
    assert payload["route_code"]
    assert len(payload["stops"]) > 0
    assert payload["stops"][0]["products"]


def test_customer_detail_uses_real_addresses() -> None:
    transport_id = client.get("/api/v1/data/transports").json()[0]["transport_id"]
    customer_id = client.get(f"/api/v1/data/transport/{transport_id}").json()["stops"][0]["customer_id"]
    response = client.get(f"/api/v1/data/customers/{customer_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["customer_id"] == customer_id
    assert payload["name"]
    assert payload["address"]


def test_routes_endpoint_summarizes_real_routes() -> None:
    response = client.get("/api/v1/data/routes")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) > 0
    assert any(item["route_code"] and item["transport_count"] > 0 for item in payload)


def test_unknown_transport_and_customer_return_404() -> None:
    transport_response = client.get("/api/v1/data/transport/does-not-exist")
    customer_response = client.get("/api/v1/data/customers/does-not-exist")

    assert transport_response.status_code == 404
    assert customer_response.status_code == 404
