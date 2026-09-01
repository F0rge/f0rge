from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://vellano:vellano@localhost:5433/vellano"
    direct_database_url: str = ""
    cors_origins: list[str] = ["http://localhost:3003"]
    jwt_secret: str = ""
    cookie_secure: bool = False
    seed_owner_email: str = "owner@example.com"
    seed_owner_password: str = "change-me-owner"

    storage_dir: str = "storage"
    bucket_name: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_endpoint_url_s3: str = ""
    aws_region: str = "auto"
    default_storage_user_id: str = "vellano"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
