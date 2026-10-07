"""
config.py — Application settings loaded from environment variables.
Uses pydantic-settings for type-safe, validated configuration.
No secrets are hardcoded here.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    # ── Application ──────────────────────────────────────────
    app_name: str = "AI-Based Warehouse Slot Utilization Analyzer"
    app_env: str = "development"
    app_port: int = 8000
    debug: bool = True

    # ── Security ─────────────────────────────────────────────
    secret_key: str = "CHANGE_THIS_IN_PRODUCTION_USE_ENV_FILE"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # ── Database ─────────────────────────────────────────────
    # Defaults to local SQLite; override with Azure SQL URL in .env
    database_url: str = "sqlite:///./warehouse.db"

    # ── Azure Blob Storage ────────────────────────────────────
    azure_storage_connection_string: str = ""
    azure_storage_account_name: str = ""
    azure_storage_container_name: str = "warehouse-datasets"

    # ── Azure Application Insights ────────────────────────────
    azure_appinsights_connection_string: str = ""

    # ── CORS ─────────────────────────────────────────────────
    allowed_origins: str = "http://localhost:8000,http://127.0.0.1:8000"

    # ── File Upload ───────────────────────────────────────────
    max_upload_size_mb: int = 50
    allowed_extensions: str = "csv"

    # ── Pagination ────────────────────────────────────────────
    default_page_size: int = 50
    max_page_size: int = 500

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    @property
    def is_azure_storage_enabled(self) -> bool:
        return bool(self.azure_storage_connection_string)

    @property
    def is_appinsights_enabled(self) -> bool:
        return bool(self.azure_appinsights_connection_string)

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance — loaded once at startup."""
    return Settings()
