from pydantic import BaseModel


class InventoryResponse(BaseModel):
    product_id: str
    available: bool
    quantity: int
    status: str


class ChaosRequest(BaseModel):
    mode: str


class ChaosResponse(BaseModel):
    mode: str
    message: str


class HealthResponse(BaseModel):
    status: str
    service: str
