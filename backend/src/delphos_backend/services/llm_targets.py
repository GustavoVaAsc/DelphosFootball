"""The two configured inference endpoints.

Input: the settings.
Output: the `InferenceTarget` of one endpoint: which one it is, where it lives,
which model id it serves and what its budget is.
Responsibility: name the endpoints the backend is configured with. Which one
serves a call is a different question, answered in `llm_choice`.
"""

from __future__ import annotations

from delphos_backend.core.config import Settings
from delphos_backend.services.llm_protocol import FALLBACK_ENDPOINT, PRIMARY_ENDPOINT
from delphos_backend.services.llm_readiness import warn_on_own_address
from delphos_backend.services.llm_request import InferenceTarget


def primary_target(cfg: Settings) -> InferenceTarget:
    """The endpoint the backend is configured to use first."""
    return InferenceTarget(
        PRIMARY_ENDPOINT, cfg.llm_api_url, cfg.llm_model_name, cfg.llm_timeout_seconds
    )


def fallback_target(cfg: Settings) -> InferenceTarget | None:
    """The second endpoint, or None when no fallback is configured."""
    url = cfg.llm_fallback_api_url.strip()
    if not url:
        return None
    return InferenceTarget(
        FALLBACK_ENDPOINT,
        url,
        cfg.llm_fallback_model_name.strip() or cfg.llm_model_name,
        cfg.llm_fallback_timeout_seconds,
    )


def target_for_kind(cfg: Settings, kind: str) -> InferenceTarget | None:
    """The configured target of one endpoint kind, None when it is not configured."""
    if kind == PRIMARY_ENDPOINT:
        return primary_target(cfg)
    if kind == FALLBACK_ENDPOINT:
        return fallback_target(cfg)
    return None


def warn_about_fallback_address(cfg: Settings) -> None:
    """Warn when the fallback names this host's own published inference address."""
    fallback = fallback_target(cfg)
    if fallback is not None:
        warn_on_own_address(cfg, fallback)
