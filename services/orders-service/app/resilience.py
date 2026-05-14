import logging
from typing import Any

import httpx
import pybreaker
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_fixed,
)

from app.config import settings
from app.metrics import (
    CIRCUIT_BREAKER_OPEN,
    FALLBACK_TOTAL,
    INVENTORY_CALLS,
    RETRY_TOTAL,
    TIMEOUT_TOTAL,
)

logger = logging.getLogger(__name__)


class _CBListener(pybreaker.CircuitBreakerListener):
    def state_change(self, cb, old_state, new_state):
        if new_state.name == "open":
            CIRCUIT_BREAKER_OPEN.inc()
            logger.warning(
                "circuit_breaker_opened",
                extra={"old_state": old_state.name, "new_state": new_state.name},
            )


circuit_breaker = pybreaker.CircuitBreaker(
    fail_max=settings.CB_FAIL_MAX,
    reset_timeout=settings.CB_RESET_TIMEOUT,
    listeners=[_CBListener()],
)


async def _raw_inventory_call(
    client: httpx.AsyncClient,
    url: str,
    request_id: str,
) -> dict:
    response = await client.get(
        url,
        headers={"X-Request-ID": request_id},
        timeout=httpx.Timeout(settings.TIMEOUT_SECONDS),
    )
    response.raise_for_status()
    return response.json()


def _on_retry(retry_state) -> None:
    RETRY_TOTAL.inc()
    logger.info(
        "inventory_call_retry",
        extra={"attempt": retry_state.attempt_number},
    )


async def call_inventory(
    product_id: str,
    request_id: str,
    client: httpx.AsyncClient,
) -> dict[str, Any] | None:
    url = f"{settings.INVENTORY_SERVICE_URL}/inventory/{product_id}"

    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(settings.RETRY_COUNT + 1),
            wait=wait_fixed(0.5),
            retry=retry_if_exception_type(
                (httpx.TimeoutException, httpx.HTTPStatusError)
            ),
            before_sleep=_on_retry,
            reraise=True,
        ):
            with attempt:
                try:
                    result = await circuit_breaker.call_async(
                        _raw_inventory_call, client, url, request_id
                    )
                    INVENTORY_CALLS.labels(outcome="success").inc()
                    return result
                except httpx.TimeoutException:
                    TIMEOUT_TOTAL.inc()
                    INVENTORY_CALLS.labels(outcome="timeout").inc()
                    logger.warning("inventory_call_timeout", extra={"url": url})
                    raise
                except httpx.HTTPStatusError as exc:
                    INVENTORY_CALLS.labels(outcome="http_error").inc()
                    logger.warning(
                        "inventory_call_http_error",
                        extra={"status_code": exc.response.status_code, "url": url},
                    )
                    raise

    except pybreaker.CircuitBreakerError:
        INVENTORY_CALLS.labels(outcome="circuit_open").inc()
        logger.warning("inventory_call_circuit_open", extra={"url": url})

    except (httpx.TimeoutException, httpx.HTTPStatusError):
        logger.error("inventory_call_all_retries_exhausted", extra={"url": url})

    except Exception as exc:
        INVENTORY_CALLS.labels(outcome="other_error").inc()
        logger.error("inventory_call_unexpected_error", extra={"error": str(exc)})

    FALLBACK_TOTAL.inc()
    return None


def get_circuit_breaker_state() -> str:
    return circuit_breaker.current_state


def get_fallback_response() -> dict:
    return {
        "status": "pending",
        "message": "Inventory service is currently unavailable. Order has been queued for later verification.",
    }
