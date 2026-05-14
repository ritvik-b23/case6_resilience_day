import time
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.config import settings
from app.logging_config import get_request_id, log_request, setup_logging
from app.metrics import HTTP_LATENCY, HTTP_REQUESTS
from app.resilience import (
    call_inventory,
    get_circuit_breaker_state,
    get_fallback_response,
)
from app.schemas import HealthResponse, OrderRequest, OrderResponse, ResilienceStatus

setup_logging()

_http_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _http_client
    _http_client = httpx.AsyncClient()
    yield
    await _http_client.aclose()


app = FastAPI(title="Orders Service", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    request_id = get_request_id(dict(request.headers))
    request.state.request_id = request_id
    start = time.perf_counter()
    response: Response = await call_next(request)
    latency_ms = (time.perf_counter() - start) * 1000
    path = request.url.path
    method = request.method
    status = response.status_code
    log_request(
        request_id=request_id,
        method=method,
        path=path,
        status_code=status,
        latency_ms=latency_ms,
    )
    HTTP_REQUESTS.labels(method=method, path=path, status_code=str(status)).inc()
    HTTP_LATENCY.labels(method=method, path=path).observe(
        (time.perf_counter() - start)
    )
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="healthy", service=settings.SERVICE_NAME)


@app.post("/orders")
async def create_order(order: OrderRequest, request: Request):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    order_id = str(uuid.uuid4())[:8]

    inventory_data = await call_inventory(
        product_id=order.product_id,
        request_id=request_id,
        client=_http_client,
    )

    if inventory_data is None:
        fallback = get_fallback_response()
        return JSONResponse(
            status_code=200,
            content={
                "order_id": order_id,
                "status": fallback["status"],
                "product_id": order.product_id,
                "quantity": order.quantity,
                "inventory_status": "unknown",
                "message": fallback["message"],
            },
        )

    available = inventory_data.get("available", False)
    if available:
        return OrderResponse(
            order_id=order_id,
            status="accepted",
            product_id=order.product_id,
            quantity=order.quantity,
            inventory_status="available",
            message="Order accepted",
        )
    else:
        return OrderResponse(
            order_id=order_id,
            status="rejected",
            product_id=order.product_id,
            quantity=order.quantity,
            inventory_status="unavailable",
            message="Order rejected: item out of stock",
        )


@app.get("/metrics")
async def metrics():
    data = generate_latest()
    return PlainTextResponse(content=data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)


@app.get("/resilience/status", response_model=ResilienceStatus)
async def resilience_status():
    return ResilienceStatus(
        retry_enabled=True,
        retry_count=settings.RETRY_COUNT,
        timeout_seconds=settings.TIMEOUT_SECONDS,
        circuit_breaker_state=get_circuit_breaker_state(),
        fallback_enabled=True,
    )
