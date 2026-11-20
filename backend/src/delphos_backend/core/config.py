"""Backend configuration loaded from environment variables and nearest .env.

Input: DELPHOS_* environment variables and .env file.
Output: Validated Settings instance.
Responsibility: Exposes typed configuration for the FastAPI service.

The fallback endpoint is guarded by an allowlist, not by a syntax check: the
peer must be an IP literal inside the configured range, so a mistyped address
cannot ship the club's prompts to a host nobody chose. The rules live in
`core/peer_policy.py`.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote_plus

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from delphos_backend.core.peer_policy import (
    check_fallback_in_range,
    validate_fallback_url,
    validate_peer_cidr,
)

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

    # Local LLM inference service settings (llama.cpp OpenAI-compatible HTTP)
    llm_api_url: str = "http://inference-chat:8080/v1"  # Base URL of the llama.cpp server
    llm_model_name: str = "qwen/qwen3.5-9b"  # Model id sent in the request body
    llm_timeout_seconds: float = 120.0  # Per-request timeout in seconds
    llm_max_tokens: int = Field(default=512, ge=1, le=8192)  # Chat completion token cap
    llm_report_max_tokens: int = Field(default=1400, ge=1, le=8192)  # Report token cap
    llm_temperature: float = 0.7  # Sampling temperature
    llm_top_p: float = 0.8  # Nucleus sampling threshold
    llm_top_k: int = 20  # Top-k sampling cutoff
    llm_presence_penalty: float = 0.0  # Repetition penalty
    llm_enable_thinking: bool = False  # Per-request thinking toggle
    llm_context_size: int = Field(default=32768, ge=1024, le=131072)  # Mirrored chat budget
    llm_max_tool_iterations: int = Field(default=4, ge=0, le=10)  # Chat tool-loop cap
    llm_max_concurrent_llm_calls: int = Field(default=4, ge=1, le=64)  # Chat LLM concurrency cap
    llm_chat_history_turns: int = Field(default=8, ge=1, le=50)  # Chat history cap in turns
    llm_report_prompt_version: str = "v2-t0.7-p0.8-k20"  # Report provenance string

    # LLM fallback endpoint: a second llama.cpp server reached over ZeroTier
    llm_fallback_api_url: str = ""  # Base URL of the fallback server; empty disables it
    llm_fallback_model_name: str = ""  # Model id sent to the fallback; empty means llm_model_name
    llm_fallback_timeout_seconds: float = Field(default=60.0, gt=0, le=600)  # Fallback budget
    llm_primary_probe_seconds: float = Field(default=5.0, gt=0, le=60)  # Probe timeout
    llm_fallback_peer_cidr: str = "10.0.0.0/8"  # The range the peer's address must sit in

    # The host address this machine publishes its inference server on. The
    # backend reads it to warn about a fallback that names this host itself.
    inference_publish_ip: str = "127.0.0.1"

    @field_validator("llm_fallback_api_url")
    @classmethod
    def _validate_fallback_api_url(cls, value: str) -> str:
        """Accept only an empty value or an http(s) URL with an IP literal host.

        A typo in the peer's address would otherwise ship the club's prompts to
        the wrong host, and the report path would degrade to the deterministic
        renderer without saying why. An invalid value fails the settings load
        with a message naming the variable.
        """
        return validate_fallback_url(value)

    @field_validator("llm_fallback_peer_cidr")
    @classmethod
    def _validate_fallback_peer_cidr(cls, value: str) -> str:
        """Accept only a CIDR the ipaddress module can parse."""
        return validate_peer_cidr(value)

    @model_validator(mode="after")
    def _validate_fallback_peer_range(self) -> Settings:
        """The fallback's address must sit inside the configured peer range.

        The range is the allowlist: a well-formed address outside it is refused,
        so a transposed peer IP or a public host never receives a prompt. The
        range is not optional when a fallback URL is set.
        """
        check_fallback_in_range(self.llm_fallback_api_url, self.llm_fallback_peer_cidr)
        return self

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
