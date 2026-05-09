from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_optimize_full_streams_websocket_result() -> None:
    response = client.post(
        "/api/v1/optimize/full",
        json={"transport_id": "11420379", "truck_type": "6pal", "solver_time_limit_s": 5},
    )

    assert response.status_code == 200
    accepted = response.json()
    assert accepted["status"] == "pending"

    messages = []
    with client.websocket_connect(accepted["ws_url"]) as websocket:
        while True:
            message = websocket.receive_json()
            messages.append(message)
            if message["type"] in {"done", "error"}:
                break

    assert [message["type"] for message in messages] == [
        "progress",
        "progress",
        "progress",
        "partial",
        "progress",
        "progress",
        "progress",
        "progress",
        "result",
        "done",
    ]
    result = next(message["result"] for message in messages if message["type"] == "result")
    assert result["job_id"] == accepted["job_id"]
    assert result["status"] == "done"
    assert result["route"]["transport_id"] == "11420379"
    assert result["load"]["pallet_slots_used"] <= result["load"]["pallet_slots_total"]
    assert result["load"]["pick_list"]


def test_job_fetch_returns_completed_result() -> None:
    response = client.post(
        "/api/v1/optimize/full",
        json={"transport_id": "11420379", "truck_type": "6pal", "solver_time_limit_s": 5},
    )
    accepted = response.json()

    with client.websocket_connect(accepted["ws_url"]) as websocket:
        while websocket.receive_json()["type"] != "done":
            pass

    result_response = client.get(f"/api/v1/jobs/{accepted['job_id']}")

    assert result_response.status_code == 200
    assert result_response.json()["status"] == "done"


def test_unknown_websocket_job_returns_error() -> None:
    with client.websocket_connect("/ws/jobs/unknown") as websocket:
        message = websocket.receive_json()

    assert message["type"] == "error"
    assert message["code"] == "JOB_NOT_FOUND"


def test_oversized_load_returns_packing_overflow() -> None:
    response = client.post(
        "/api/v1/optimize/full",
        json={"transport_id": "11515121", "truck_type": "6pal", "solver_time_limit_s": 5},
    )
    accepted = response.json()

    with client.websocket_connect(accepted["ws_url"]) as websocket:
        while True:
            message = websocket.receive_json()
            if message["type"] == "error":
                break

    assert message["code"] == "PACKING_OVERFLOW"
