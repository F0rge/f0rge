from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://firstout:firstout@localhost:5433/firstout"
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
    # Role logins, the storefront system user, and the Walk-in customer.
    # Off so a wiped database stays wiped. Owner bootstrap is separate.
    seed_boot_fixtures: bool = False
    seed_playground: bool = False
    # Background loop that emails overdue invoices. Tests turn this off.
    payment_reminder_ticker: bool = True

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Fallback when openrouter_document_model is empty.
    openrouter_model: str = "openai/gpt-4o-mini"
    # Vision-capable model for supplier proforma and invoice reading.
    # Text-layer PDFs are sent as text; photos and scans go to this model as images.
    openrouter_document_model: str = "openai/gpt-4o-mini"
    # Accepted for operators who set them. The document reader posts temperature 0
    # and does not send OpenRouter reasoning flags.
    openrouter_reasoning_effort: str = "low"
    openrouter_reasoning_exclude: bool = True
    settings_encryption_key: str = ""
    wa_verify_token: str = ""

    storage_dir: str = "storage"
    bucket_name: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_endpoint_url_s3: str = ""
    aws_region: str = "auto"
    default_storage_user_id: str = "firstout"
    ops_commerce_token: str = ""
    ops_commerce_company_id: str = ""
    ops_commerce_allowed_host: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
