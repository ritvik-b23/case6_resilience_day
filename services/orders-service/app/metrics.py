from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter(
    "orders_http_requests_total",
    "Total HTTP requests to orders-service",
    ["method", "path", "status_code"],
)

HTTP_LATENCY = Histogram(
    "orders_http_request_duration_seconds",
    "HTTP request latency for orders-service",
    ["method", "path"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)

INVENTORY_CALLS = Counter(
    "orders_inventory_calls_total",
    "Total calls to inventory-service from orders-service",
    ["outcome"],
)

RETRY_TOTAL = Counter(
    "orders_retry_total",
    "Total retry attempts made by orders-service",
)

TIMEOUT_TOTAL = Counter(
    "orders_timeout_total",
    "Total timeout events when calling inventory-service",
)

CIRCUIT_BREAKER_OPEN = Counter(
    "orders_circuit_breaker_open_total",
    "Total times the circuit breaker transitioned to open state",
)

FALLBACK_TOTAL = Counter(
    "orders_fallback_total",
    "Total fallback responses returned by orders-service",
)
