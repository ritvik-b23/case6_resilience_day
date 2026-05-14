from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter(
    "inventory_http_requests_total",
    "Total HTTP requests to inventory-service",
    ["method", "path", "status_code"],
)

HTTP_LATENCY = Histogram(
    "inventory_http_request_duration_seconds",
    "HTTP request latency for inventory-service",
    ["method", "path"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)

INVENTORY_LOOKUPS = Counter(
    "inventory_lookups_total",
    "Total inventory lookup requests",
    ["product_id", "result"],
)
