from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_data_health_reports_real_counts() -> None:
    response = client.get("/api/v1/data/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "data_loaded": True,
        "customer_count": 1203,
        "transport_count": 889,
        "geocoded_count": 0,
    }


def test_list_transports_returns_real_transport_summaries() -> None:
    response = client.get("/api/v1/data/transports")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 889
    assert any(item["transport_id"] == "11515121" and item["stop_count"] == 32 for item in payload)


def test_transport_detail_uses_real_source_rows() -> None:
    response = client.get("/api/v1/data/transport/11515121")

    assert response.status_code == 200
    payload = response.json()
    assert payload["route_code"] == "DR0045"
    assert len(payload["stops"]) == 32
    assert payload["stops"][0]["products"][0]["material_code"] == "ED15LN"


def test_customer_detail_uses_real_addresses() -> None:
    response = client.get("/api/v1/data/customers/9100054949")

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "XARRUP BAR"
    assert payload["lat"] is None
    assert payload["lng"] is None


def test_routes_endpoint_summarizes_real_routes() -> None:
    response = client.get("/api/v1/data/routes")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 18
    assert any(item["route_code"] == "DR0045" and item["transport_count"] > 0 for item in payload)


def test_unknown_transport_and_customer_return_404() -> None:
    transport_response = client.get("/api/v1/data/transport/does-not-exist")
    customer_response = client.get("/api/v1/data/customers/does-not-exist")

    assert transport_response.status_code == 404
    assert customer_response.status_code == 404
