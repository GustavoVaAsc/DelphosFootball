"""Unit tests for backend settings and configuration."""

from __future__ import annotations

from delphos_backend.core.config import Settings


def test_default_settings() -> None:
    settings = Settings()
    assert settings.db_host == "localhost"
    assert settings.db_port == 5432
    assert settings.db_name == "delphos"
    assert settings.app_db_user == "delphos_app_user"
    assert settings.api_port == 8000
    assert "http://localhost" in settings.cors_origins_list


def test_custom_database_url_normalization() -> None:
    settings = Settings(app_database_url="postgresql+psycopg://user:pw@host:5432/db")
    url = settings.get_database_url()
    assert url.startswith("postgresql://user:pw@host:5432/db")
