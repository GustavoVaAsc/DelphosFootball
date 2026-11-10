"""Unit tests for backend settings and configuration."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("llm_max_tool_iterations", -1),
        ("llm_max_tool_iterations", 11),
        ("llm_chat_history_turns", 0),
        ("llm_chat_history_turns", 51),
        ("llm_max_tokens", 0),
        ("llm_max_tokens", 8193),
        ("llm_report_max_tokens", 0),
        ("llm_report_max_tokens", 8193),
        ("llm_context_size", 512),
        ("llm_context_size", 131073),
        ("llm_max_concurrent_llm_calls", 0),
        ("llm_max_concurrent_llm_calls", 65),
    ],
)
def test_llm_numeric_settings_reject_out_of_range_values(field: str, value: int) -> None:
    """The LLM budget settings cannot be set to a nonsensical value."""
    with pytest.raises(ValidationError):
        Settings(**{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("llm_max_tool_iterations", 0),
        ("llm_max_tool_iterations", 10),
        ("llm_chat_history_turns", 1),
        ("llm_chat_history_turns", 50),
        ("llm_max_tokens", 1),
        ("llm_max_tokens", 8192),
        ("llm_report_max_tokens", 1),
        ("llm_report_max_tokens", 8192),
        ("llm_context_size", 1024),
        ("llm_context_size", 131072),
        ("llm_max_concurrent_llm_calls", 1),
        ("llm_max_concurrent_llm_calls", 64),
    ],
)
def test_llm_numeric_settings_accept_boundary_values(field: str, value: int) -> None:
    """The documented bounds are inclusive."""
    assert getattr(Settings(**{field: value}), field) == value


def test_concurrency_cap_is_configured_through_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The chat concurrency cap is a Settings knob, not a private env lookup."""
    monkeypatch.setenv("DELPHOS_LLM_MAX_CONCURRENT_LLM_CALLS", "7")

    settings = Settings()

    assert settings.llm_max_concurrent_llm_calls == 7
