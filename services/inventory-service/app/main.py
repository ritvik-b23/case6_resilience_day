import time

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.chaos import (
    ALLOWED_MODES,
    ChaosError,
    ChaosUnavailableError,
    apply_chaos,
    get_mode,
    set_mode,
)
from app.config import settings
from app.logging_config import get_request_id, log_request, setup_logging
from app.metrics import HTTP_LATENCY, HTTP_REQUESTS, INVENTORY_LOOKUPS
from app.schemas import (
    ChaosRequest,
    ChaosResponse,
    HealthResponse,
    InventoryResponse,
)

setup_logging()

app = FastAPI(title="Inventory Service", version="1.0.0")


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    request_id = get_request_id(dict(request.headers))
    request.state.request_id = request_id
    start = time.perf_counter()
    response: Response = await call_next(request)
    elapsed = time.perf_counter() - start
    latency_ms = elapsed * 1000
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
    HTTP_LATENCY.labels(method=method, path=path).observe(elapsed)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="healthy", service=settings.SERVICE_NAME)


@app.get("/inventory/{product_id}", response_model=InventoryResponse)
async def get_inventory(product_id: str, request: Request):
    try:
        await apply_chaos()
    except ChaosError as exc:
        INVENTORY_LOOKUPS.labels(product_id=product_id, result="error").inc()
        raise HTTPException(status_code=500, detail=str(exc))
    except ChaosUnavailableError:
        INVENTORY_LOOKUPS.labels(product_id=product_id, result="unavailable").inc()
        return InventoryResponse(
            product_id=product_id,
            available=False,
            quantity=0,
            status="unavailable",
        )

    INVENTORY_LOOKUPS.labels(product_id=product_id, result="available").inc()
    return InventoryResponse(
        product_id=product_id,
        available=True,
        quantity=100,
        status="available",
    )


@app.post("/chaos/mode", response_model=ChaosResponse)
async def set_chaos_mode(body: ChaosRequest):
    if body.mode not in ALLOWED_MODES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid mode '{body.mode}'. Allowed: {sorted(ALLOWED_MODES)}",
        )
    set_mode(body.mode)
    return ChaosResponse(mode=body.mode, message=f"Chaos mode set to '{body.mode}'")


@app.get("/chaos/mode", response_model=ChaosResponse)
async def get_chaos_mode():
    mode = get_mode()
    return ChaosResponse(mode=mode, message=f"Current chaos mode: '{mode}'")


@app.get("/metrics")
async def metrics():
    data = generate_latest()
    return PlainTextResponse(content=data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)
