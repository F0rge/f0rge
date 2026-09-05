from __future__ import annotations

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://vellano:vellano@localhost:5433/vellano"
    direct_database_url: str = ""
    cors_origins: list[str] = ["http://localhost:3003"]
    jwt_secret: str = ""
    cookie_secure: bool = False
    seed_owner_email: str = "owner@example.com"
    seed_owner_password: str = "change-me-owner"
    seed_till_password: str = "change-me-till"
    seed_books_password: str = "change-me-books"
    seed_warehouse_password: str = "change-me-warehouse"
    seed_buyer_password: str = "change-me-buyer"
    seed_playground: bool = False

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "openai/gpt-4o-mini"
    # OpenRouter unified reasoning (pydantic-ai openrouter_reasoning → extra_body.reasoning).
    # GLM-5.3 / glm-5.3-flash always reason; effort low|high|max (default max upstream).
    openrouter_reasoning_effort: str = "low"
    # When true, set reasoning.exclude (clear_thinking) so thinking is not in content.
    openrouter_reasoning_exclude: bool = True
    nia_schedule_ticker: bool = True

    storage_dir: str = "storage"
    bucket_name: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_endpoint_url_s3: str = ""
    aws_region: str = "auto"
    default_storage_user_id: str = "vellano"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
