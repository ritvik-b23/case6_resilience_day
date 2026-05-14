"""Tests for resilience mechanisms: timeout, retry, circuit breaker, fallback."""
import httpx
import pytest
import pybreaker
from unittest.mock import AsyncMock, MagicMock, patch

from app.resilience import call_inventory, circuit_breaker, get_circuit_breaker_state


@pytest.fixture(autouse=True)
def reset_circuit_breaker():
    """Reset circuit breaker state before each test."""
    circuit_breaker.close()
    yield
    circuit_breaker.close()


@pytest.mark.asyncio
async def test_returns_data_on_success():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    inventory_data = {"product_id": "P001", "available": True, "quantity": 100}

    with patch("app.resilience._raw_inventory_call", new_callable=AsyncMock) as mock_raw:
        mock_raw.return_value = inventory_data
        result = await call_inventory("P001", "req-123", mock_client)

    assert result == inventory_data


@pytest.mark.asyncio
async def test_returns_none_on_timeout():
    mock_client = AsyncMock(spec=httpx.AsyncClient)

    with patch("app.resilience._raw_inventory_call", new_callable=AsyncMock) as mock_raw:
        mock_raw.side_effect = httpx.TimeoutException("timed out")
        result = await call_inventory("P001", "req-123", mock_client)

    assert result is None


@pytest.mark.asyncio
async def test_returns_none_on_http_500():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = MagicMock()
    mock_response.status_code = 500

    with patch("app.resilience._raw_inventory_call", new_callable=AsyncMock) as mock_raw:
        mock_raw.side_effect = httpx.HTTPStatusError(
            "500 error", request=MagicMock(), response=mock_response
        )
        result = await call_inventory("P001", "req-123", mock_client)

    assert result is None


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_repeated_failures():
    """After fail_max failures, the circuit should open and subsequent calls return None immediately."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = MagicMock()
    mock_response.status_code = 500

    # Exhaust retries enough times to open the circuit breaker (fail_max=3)
    with patch("app.resilience._raw_inventory_call", new_callable=AsyncMock) as mock_raw:
        mock_raw.side_effect = httpx.HTTPStatusError(
            "500 error", request=MagicMock(), response=mock_response
        )
        # Each call_inventory exhausts retries (3 attempts) → 1 failure counted per call_inventory
        for _ in range(3):
            await call_inventory("P001", "req-123", mock_client)

    # Circuit should now be open
    assert get_circuit_breaker_state() == "open"

    # Next call should return None immediately (circuit open, no actual HTTP call)
    with patch("app.resilience._raw_inventory_call", new_callable=AsyncMock) as mock_raw:
        mock_raw.return_value = {"available": True}
        result = await call_inventory("P001", "req-123", mock_client)

    assert result is None
    # The raw call should NOT have been made because circuit is open
    mock_raw.assert_not_called()


def test_get_circuit_breaker_state_returns_string():
    state = get_circuit_breaker_state()
    assert state in {"closed", "open", "half-open"}
