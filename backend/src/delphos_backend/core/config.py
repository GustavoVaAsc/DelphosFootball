"""Backend configuration loaded from environment variables and nearest .env.

Input: DELPHOS_* environment variables and .env file.
Output: Validated Settings instance.
Responsibility: Exposes typed configuration for the FastAPI service.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PREFIX = "DELPHOS_"


class Settings(BaseSettings):
    """Configuration for the DelphosFootball FastAPI backend."""

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX,
        extra="ignore",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Database connection parameters (app role: reads analytics, writes app)
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "delphos"
    app_db_user: str = "delphos_app_user"
    app_db_password: str = "delphos_app_user_secret"
    app_database_url: str | None = None

    # Server settings
    api_port: int = 8000
    cors_origins: str = "http://localhost,http://localhost:80,http://localhost:3000"
    artifacts_dir: Path | None = None

    @property
    def cors_origins_list(self) -> list[str]:
        """Return CORS allowed origins as a parsed list of strings."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def get_database_url(self) -> str:
        """Return the normalized PostgreSQL connection string for delphos_app_user."""
        if self.app_database_url:
            return self.app_database_url.replace("postgresql+psycopg://", "postgresql://")
        user = quote_plus(self.app_db_user)
        pw = quote_plus(self.app_db_password)
        return f"postgresql://{user}:{pw}@{self.db_host}:{self.db_port}/{self.db_name}"


def get_settings() -> Settings:
    """Return a cached or freshly instantiated Settings object."""
    return Settings()

