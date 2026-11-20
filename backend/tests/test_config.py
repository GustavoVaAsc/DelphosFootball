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


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("llm_fallback_timeout_seconds", 0.0),
        ("llm_fallback_timeout_seconds", 600.1),
        ("llm_primary_probe_seconds", 0.0),
        ("llm_primary_probe_seconds", 60.1),
    ],
)
def test_llm_fallback_settings_reject_out_of_range_values(field: str, value: float) -> None:
    """The fallback budget and the probe timeout cannot be set to a nonsensical value."""
    with pytest.raises(ValidationError):
        Settings(**{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("llm_fallback_timeout_seconds", 0.1),
        ("llm_fallback_timeout_seconds", 600.0),
        ("llm_primary_probe_seconds", 0.1),
        ("llm_primary_probe_seconds", 60.0),
    ],
)
def test_llm_fallback_settings_accept_boundary_values(field: str, value: float) -> None:
    """The documented bounds are inclusive."""
    assert getattr(Settings(**{field: value}), field) == value


def test_the_fallback_endpoint_is_disabled_by_default() -> None:
    """An empty fallback URL keeps the backend on its single configured endpoint."""
    settings = Settings()

    assert settings.llm_fallback_api_url == ""
    assert settings.llm_fallback_model_name == ""
    assert settings.llm_fallback_timeout_seconds == 60.0
    assert settings.llm_primary_probe_seconds == 5.0
    assert settings.llm_fallback_peer_cidr == "10.0.0.0/8"


@pytest.mark.parametrize(
    "value",
    [
        "ftp://10.147.85.4/v1",
        "10.147.85.4:8081/v1",
        "http://",
        "http://user:pass@10.147.85.4/v1",
        "http://10.147.85.4/v1 with space",
        "http://10.147.85.4/v1?api_key=secret",
        "http://10.147.85.4/v1#fragment",
    ],
    ids=["scheme", "no-scheme", "no-host", "credentials", "whitespace", "query", "fragment"],
)
def test_an_invalid_fallback_url_fails_the_settings_load(value: str) -> None:
    """A typo in the peer's address must not ship the club's prompts to the wrong host."""
    with pytest.raises(ValidationError) as excinfo:
        Settings(llm_fallback_api_url=value)

    assert "DELPHOS_LLM_FALLBACK_API_URL" in str(excinfo.value)


@pytest.mark.parametrize(
    "value",
    [
        "http://peer.test:8081/v1",
        "https://peer.test/v1",
        "http://peer.test",
    ],
    ids=["http-hostname", "https-hostname", "bare-hostname"],
)
def test_a_fallback_url_with_a_hostname_fails_the_settings_load(value: str) -> None:
    """A hostname could resolve anywhere, and DNS would defeat the allowlist."""
    with pytest.raises(ValidationError) as excinfo:
        Settings(llm_fallback_api_url=value)

    assert "DELPHOS_LLM_FALLBACK_API_URL" in str(excinfo.value)
    assert "IP address" in str(excinfo.value)


@pytest.mark.parametrize(
    "value",
    [
        "http://8.8.8.8/v1",
        "http://172.16.4.1/v1",
        "http://192.168.1.10/v1",
        "http://[2001:db8::1]/v1",
        "http://[fe80::1]/v1",
    ],
    ids=[
        "public",
        "outside-range",
        "private-outside-range",
        "ipv6-outside-range",
        "ipv6-link-local",
    ],
)
def test_a_fallback_url_outside_the_peer_range_fails_the_settings_load(value: str) -> None:
    """The peer range is the allowlist: an address outside it is refused."""
    with pytest.raises(ValidationError) as excinfo:
        Settings(llm_fallback_api_url=value)

    assert "DELPHOS_LLM_FALLBACK_API_URL" in str(excinfo.value)


@pytest.mark.parametrize(
    "value",
    [
        "http://127.0.0.1:8081/v1",
        "http://169.254.10.1/v1",
        "http://0.0.0.0:8081/v1",
        "http://239.1.2.3:8081/v1",
        "http://240.0.0.1:8081/v1",
        "http://[::1]:8081/v1",
    ],
    ids=["loopback", "link-local", "unspecified", "multicast", "reserved", "ipv6-loopback"],
)
def test_a_fallback_url_naming_an_unreachable_address_fails_the_settings_load(value: str) -> None:
    """None of these addresses ever names another machine."""
    with pytest.raises(ValidationError) as excinfo:
        Settings(llm_fallback_api_url=value)

    assert "DELPHOS_LLM_FALLBACK_API_URL" in str(excinfo.value)


@pytest.mark.parametrize(
    "value",
    ["http://10.147.85.4:8081/v1", "https://10.147.85.4/v1", "http://10.147.85.4"],
    ids=["http", "https", "no-port"],
)
def test_a_valid_fallback_url_is_accepted(value: str) -> None:
    """An empty value disables the fallback; an IP inside the range enables it."""
    assert Settings(llm_fallback_api_url=value).llm_fallback_api_url == value


def test_an_empty_fallback_url_is_accepted() -> None:
    """An empty value disables the fallback entirely."""
    assert Settings(llm_fallback_api_url="").llm_fallback_api_url == ""


def test_an_address_inside_a_wider_peer_range_is_accepted() -> None:
    """The peer range is configurable: the ZeroTier network's own range fits."""
    settings = Settings(
        llm_fallback_api_url="http://10.147.85.4:8081/v1",
        llm_fallback_peer_cidr="10.147.0.0/16",
    )

    assert settings.llm_fallback_peer_cidr == "10.147.0.0/16"


@pytest.mark.parametrize("cidr", ["", "not-a-cidr", "10.0.0.0/33", "10.0.0.0/8/8"])
def test_an_invalid_peer_range_fails_the_settings_load(cidr: str) -> None:
    """The range is the allowlist, so a broken one must not be ignored."""
    with pytest.raises(ValidationError) as excinfo:
        Settings(llm_fallback_api_url="http://10.147.85.4:8081/v1", llm_fallback_peer_cidr=cidr)

    assert "DELPHOS_LLM_FALLBACK_PEER_CIDR" in str(excinfo.value)


def test_an_empty_peer_range_fails_the_settings_load_when_a_fallback_is_set() -> None:
    """The allowlist is not optional: a fallback without a range is a configuration error."""
    with pytest.raises(ValidationError) as excinfo:
        Settings(llm_fallback_api_url="http://10.147.85.4:8081/v1", llm_fallback_peer_cidr="")

    assert "DELPHOS_LLM_FALLBACK_PEER_CIDR" in str(excinfo.value)


def test_an_empty_peer_range_is_accepted_without_a_fallback() -> None:
    """Without a fallback there is no peer to allow, so the range does not matter."""
    assert Settings(llm_fallback_peer_cidr="").llm_fallback_peer_cidr == ""
