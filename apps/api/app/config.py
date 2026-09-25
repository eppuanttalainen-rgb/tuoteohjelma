from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Machine Compliance Intelligence API"
    environment: str = "development"
    database_url: str = (
        "postgresql+asyncpg://machine_intelligence:"
        "machine_intelligence_dev@db:5432/machine_intelligence"
    )
    web_origin: str = "http://localhost:3000"
    storage_root: Path = Path("./data/evidence")
    max_upload_mb: int = 50

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
