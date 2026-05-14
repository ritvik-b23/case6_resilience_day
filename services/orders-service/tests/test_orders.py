from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

ORDER_PAYLOAD = {"customer_id": "C001", "product_id": "P001", "quantity": 2}
INVENTORY_AVAILABLE = {"product_id": "P001", "available": True, "quantity": 100, "status": "available"}
INVENTORY_UNAVAILABLE = {"product_id": "P001", "available": False, "quantity": 0, "status": "unavailable"}


def test_order_accepted_when_inventory_available():
    with patch("app.main.call_inventory", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = INVENTORY_AVAILABLE
        response = client.post("/orders", json=ORDER_PAYLOAD)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert data["inventory_status"] == "available"
    assert data["product_id"] == "P001"
    assert data["quantity"] == 2


def test_order_rejected_when_inventory_unavailable():
    with patch("app.main.call_inventory", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = INVENTORY_UNAVAILABLE
        response = client.post("/orders", json=ORDER_PAYLOAD)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "rejected"
    assert data["inventory_status"] == "unavailable"


def test_order_fallback_when_inventory_unreachable():
    with patch("app.main.call_inventory", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = None
        response = client.post("/orders", json=ORDER_PAYLOAD)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending"
    assert "queued" in data["message"].lower()


def test_order_missing_fields_returns_422():
    response = client.post("/orders", json={"customer_id": "C001"})
    assert response.status_code == 422


def test_resilience_status_endpoint():
    response = client.get("/resilience/status")
    assert response.status_code == 200
    data = response.json()
    assert data["retry_enabled"] is True
    assert data["fallback_enabled"] is True
    assert "circuit_breaker_state" in data
