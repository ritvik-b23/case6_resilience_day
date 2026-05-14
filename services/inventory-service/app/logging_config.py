import logging

from pythonjsonlogger import jsonlogger

from app.config import settings


def setup_logging() -> None:
    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


def get_request_id(headers: dict) -> str:
    import uuid

    return headers.get("x-request-id") or str(uuid.uuid4())


def log_request(
    *,
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    latency_ms: float,
    error: str | None = None,
) -> None:
    extra: dict = {
        "service": settings.SERVICE_NAME,
        "request_id": request_id,
        "method": method,
        "path": path,
        "status_code": status_code,
        "latency_ms": round(latency_ms, 2),
    }
    if error:
        extra["error"] = error
    logging.getLogger("access").info("request_processed", extra=extra)
