from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    pin_hash: str = ""
    vault_path: str = (
        "/Users/leo/Library/Mobile Documents"
        "/iCloud~md~obsidian/Documents/Health-Research"
    )
    database_url: str = "sqlite:///data/health.db"
    secret_key: str = "change-me"
    cors_origins: list[str] = ["http://localhost:3000"]
    photo_dir: str = "photos"
    openweathermap_api_key: str = ""
    openweathermap_city: str = "Luxembourg"
    weather_fetch_enabled: bool = True
    health_import_token: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()
