from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "orders-service"
    INVENTORY_SERVICE_URL: str = "http://inventory-service:8002"
    TIMEOUT_SECONDS: float = 1.0
    RETRY_COUNT: int = 2
    CB_FAIL_MAX: int = 3
    CB_RESET_TIMEOUT: int = 15

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
