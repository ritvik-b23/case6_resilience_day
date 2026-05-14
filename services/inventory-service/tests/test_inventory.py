import pytest
from fastapi.testclient import TestClient

from app.chaos import set_mode
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_chaos_mode():
    set_mode("normal")
    yield
    set_mode("normal")


def test_inventory_normal_mode_returns_available():
    response = client.get("/inventory/P001")
    assert response.status_code == 200
    data = response.json()
    assert data["available"] is True
    assert data["product_id"] == "P001"


def test_inventory_error_mode_returns_500():
    set_mode("error")
    response = client.get("/inventory/P001")
    assert response.status_code == 500


def test_inventory_unavailable_mode_returns_200_not_available():
    set_mode("unavailable")
    response = client.get("/inventory/P001")
    assert response.status_code == 200
    data = response.json()
    assert data["available"] is False
    assert data["status"] == "unavailable"


def test_chaos_mode_get_returns_current_mode():
    response = client.get("/chaos/mode")
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "normal"


def test_chaos_mode_set_to_slow():
    response = client.post("/chaos/mode", json={"mode": "slow"})
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "slow"


def test_chaos_mode_set_to_flaky():
    response = client.post("/chaos/mode", json={"mode": "flaky"})
    assert response.status_code == 200
    assert response.json()["mode"] == "flaky"


def test_chaos_mode_invalid_returns_422():
    response = client.post("/chaos/mode", json={"mode": "explode"})
    assert response.status_code == 422


def test_metrics_endpoint_returns_text():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "inventory_http_requests_total" in response.text


def test_slow_mode_reports_mode_correctly():
    set_mode("slow")
    response = client.get("/chaos/mode")
    assert response.json()["mode"] == "slow"
