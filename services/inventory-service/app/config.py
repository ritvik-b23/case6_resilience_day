from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SERVICE_NAME: str = "inventory-service"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
