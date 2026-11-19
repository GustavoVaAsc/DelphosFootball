"""Async OpenAI-compatible client for the local llama.cpp inference server.

Input: chat messages plus per-call sampling options (max_tokens, thinking, seed).
Output: CompletionResult with the content, the usage, the timings and the
provenance of the call: the endpoint that served it and the model id asked for.
Responsibility: choose the endpoint that serves a call — the configured primary,
or the remote fallback over ZeroTier when the primary cannot serve it — and hand
the call to it. Every failure mode arrives as InferenceError (never
fastapi.HTTPException), so callers can degrade to the deterministic report with a
200 (LLM_PLAN §7.1). The protocol types are re-exported from `llm_protocol`, so
the callers keep one import path.

The endpoint is decided before the answer of that call exists, and it is pinned
for the whole turn: `resolve_target` decides once, and the caller that owns a
turn (the chat tool loop) passes that decision down, so one turn is never
composed of two models' output and the tool results never cross to the peer
mid-turn (ADR-033). A call that fails before it produced an answer may still be
handed to the peer, because no answer of it exists yet.

The peer is probed like the primary: it is used only when its own probe says it
is serving, so a dead or wrong address never receives a prompt.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from delphos_backend.core.config import Settings, get_settings
from delphos_backend.services.llm_attempts import attempt, compose_failure, serve_on_fallback
from delphos_backend.services.llm_choice import (
    decide_target,
    peer_target,
    resolve_target,
)
from delphos_backend.services.llm_endpoint import endpoint_label
from delphos_backend.services.llm_protocol import (
    FALLBACK_ENDPOINT,
    PRIMARY_ENDPOINT,
    CompletionResult,
    InferenceError,
    InferenceTimeout,
    Timings,
    TokenUsage,
)
from delphos_backend.services.llm_request import CallOptions, InferenceTarget

__all__ = [
    "FALLBACK_ENDPOINT",
    "PRIMARY_ENDPOINT",
    "CompletionResult",
    "InferenceError",
    "InferenceTimeout",
    "InferenceTarget",
    "TokenUsage",
    "Timings",
    "chat_completion",
    "resolve_target",
]

logger = logging.getLogger(__name__)


async def chat_completion(
    messages: list[dict[str, Any]],
    *,
    settings: Settings | None = None,
    max_tokens: int | None = None,
    enable_thinking: bool | None = None,
    seed: int | None = None,
    response_format: dict[str, Any] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    target: InferenceTarget | None = None,
) -> CompletionResult:
    """Post one non-streaming chat completion; raise InferenceError on any failure.

    max_tokens defaults to Settings.llm_max_tokens (chat); the report path passes
    llm_report_max_tokens. enable_thinking defaults to Settings.llm_enable_thinking
    and is sent per request so report and chat can differ. seed and response_format
    are sent only when supplied. transport exists for tests (httpx.MockTransport).

    Without a fallback endpoint this is one call to the primary, as it always was.
    With one, the primary is probed first: an endpoint that is not serving is
    skipped without paying its timeout, and a primary that fails mid-call is
    retried on the fallback, with the fallback's own budget. The fallback is
    probed before it is given anything, so a dead or wrong address never
    receives a prompt.

    `target` pins the endpoint: the call goes to that endpoint and is never
    handed to the peer, which is what keeps one turn on one endpoint.
    """
    cfg = settings or get_settings()
    options = CallOptions(messages, max_tokens, enable_thinking, seed, response_format)
    if target is not None:
        return await attempt(target, options, cfg, transport)
    chosen, probe = await decide_target(cfg, transport)
    if chosen.kind != PRIMARY_ENDPOINT:
        return await serve_on_fallback(chosen, probe, options, cfg, transport)
    try:
        return await attempt(chosen, options, cfg, transport)
    except InferenceError as primary_error:
        fallback, peer_error = await peer_target(cfg, chosen, transport)
        if fallback is None:
            if peer_error is None:
                raise
            message = (
                f"LLM call failed on both endpoints: primary: {primary_error}; "
                f"fallback: {peer_error}"
            )
            raise compose_failure(primary_error, peer_error, message) from primary_error
        logger.warning(
            "The primary inference call failed (%s); the fallback %s serves the call",
            primary_error,
            endpoint_label(fallback.base_url),
        )
        try:
            return await attempt(fallback, options, cfg, transport)
        except InferenceError as fallback_error:
            message = (
                f"LLM call failed on both endpoints: primary: {primary_error}; "
                f"fallback: {fallback_error}"
            )
            raise compose_failure(primary_error, fallback_error, message) from primary_error
