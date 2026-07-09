from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    pin_hash: str = ""
    database_url: str = "postgresql+asyncpg://health:health@localhost:5432/health"
    direct_database_url: str = ""
    app_timezone: str = "Europe/Luxembourg"
    settings_encryption_key: str = ""
    cors_origins: list[str] = ["http://localhost:3000"]
    photo_dir: str = "photos"
    openweathermap_api_key: str = ""
    openweathermap_city: str = "Luxembourg"
    weather_fetch_enabled: bool = True
    health_import_token: str = ""
    openrouter_api_key: str = ""
    openrouter_model: str = "google/gemini-3-flash-preview"
    food_analysis_enabled: bool = True
    mcp_readonly_database_url: str = ""
    mcp_server_host: str = "0.0.0.0"
    mcp_server_port: int = 8005
    embedding_worker_poll_interval_seconds: int = 5
    embedding_worker_batch_size: int = 10
    embedding_worker_max_attempts: int = 5

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
