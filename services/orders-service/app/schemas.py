from pydantic import BaseModel


class OrderRequest(BaseModel):
    customer_id: str
    product_id: str
    quantity: int


class OrderResponse(BaseModel):
    order_id: str
    status: str
    product_id: str
    quantity: int
    inventory_status: str
    message: str


class ResilienceStatus(BaseModel):
    retry_enabled: bool
    retry_count: int
    timeout_seconds: float
    circuit_breaker_state: str
    fallback_enabled: bool


class HealthResponse(BaseModel):
    status: str
    service: str
