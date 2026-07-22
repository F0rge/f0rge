from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    jwt_secret: str = ""
    database_url: str = "postgresql+asyncpg://health:health@localhost:5432/health"
    direct_database_url: str = ""
    app_timezone: str = "Europe/Luxembourg"
    settings_encryption_key: str = ""
    cors_origins: list[str] = ["http://localhost:3000"]
    photo_dir: str = "photos"
    bucket_name: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_endpoint_url_s3: str = ""
    aws_region: str = "auto"
    default_storage_user_id: str = "00000000-0000-0000-0000-000000000001"
    openweathermap_api_key: str = ""
    openweathermap_city: str = "Luxembourg"
    weather_fetch_enabled: bool = True
    health_import_token: str = ""
    dose_reminders_enabled: bool = True
    apns_key_id: str = ""
    apns_team_id: str = ""
    apns_private_key: str = ""  # .p8 PEM content, not a path
    apns_topic: str = "com.f0rge.marrow"
    apns_use_sandbox: bool = True
    openrouter_api_key: str = ""
    openrouter_model: str = "google/gemini-3-flash-preview"
    food_analysis_enabled: bool = True
    mcp_readonly_database_url: str = ""
    mcp_server_host: str = "0.0.0.0"
    mcp_server_port: int = 8005
    sentry_dsn: str = ""
    embedding_worker_poll_interval_seconds: int = 5
    embedding_worker_batch_size: int = 10
    embedding_worker_max_attempts: int = 5
    redis_url: str = ""
    cache_ttl_catalog_seconds: int = 3600
    cache_ttl_entry_seconds: int = 300
    cache_ttl_feature_matrix_seconds: int = 600

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
