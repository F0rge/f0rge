from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://vellano:vellano@localhost:5433/vellano"
    direct_database_url: str = ""
    cors_origins: list[str] = ["http://localhost:3003"]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
