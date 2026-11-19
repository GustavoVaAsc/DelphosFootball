"""One attempt at a completion, and the error two failed attempts compose.

Input: an endpoint target, the per-call options, the settings and an optional transport.
Output: a CompletionResult, or the InferenceError that names both failures.
Responsibility: post one completion to one endpoint, record what the answer means
for the probe cache and for the logs, and compose the error of two failed
attempts: a timeout when both of them were timeouts, so the report path spends
no repair attempt on them (ADR-033).

A primary attempt drops the cached verdict of the primary whether it answered or
failed: a verdict of up to five seconds about an endpoint that just refused to
answer is the wrong thing to trust.
"""

from __future__ import annotations

import logging

import httpx

from delphos_backend.core.config import Settings
from delphos_backend.services.llm_endpoint import endpoint_label, post_completion
from delphos_backend.services.llm_probe import ProbeResult, invalidate_probe
from delphos_backend.services.llm_protocol import (
    FALLBACK_ENDPOINT,
    CompletionResult,
    InferenceError,
    InferenceTimeout,
)
from delphos_backend.services.llm_request import CallOptions, InferenceTarget

logger = logging.getLogger(__name__)


async def attempt(
    target: InferenceTarget,
    options: CallOptions,
    cfg: Settings,
    transport: httpx.AsyncBaseTransport | None,
) -> CompletionResult:
    """Post one completion to one endpoint and record what the answer implies."""
    try:
        result = await post_completion(target, options, cfg, transport)
    except Exception:
        # A failed attempt contradicts a cached "serving" verdict, so the next
        # request probes again instead of trusting a verdict of up to five
        # seconds. A successful attempt keeps it: the endpoint has just
        # answered.
        invalidate_probe(target.base_url)
        raise
    if target.kind == FALLBACK_ENDPOINT:
        logger.warning(
            "The fallback inference endpoint %s served the call", endpoint_label(target.base_url)
        )
    return result


async def serve_on_fallback(
    fallback: InferenceTarget,
    probe: ProbeResult | None,
    options: CallOptions,
    cfg: Settings,
    transport: httpx.AsyncBaseTransport | None,
) -> CompletionResult:
    """Serve the call on the fallback, and report both failures when it fails too."""
    try:
        return await attempt(fallback, options, cfg, transport)
    except InferenceError as fallback_error:
        reason = probe.reason if probe is not None else "the endpoint did not answer"
        primary_error = (
            InferenceTimeout(f"the primary endpoint did not answer the probe: {reason}")
            if probe is not None and probe.timed_out
            else InferenceError(f"the primary endpoint is unreachable: {reason}")
        )
        message = (
            "LLM call failed: the primary endpoint is unreachable "
            f"({reason}) and the fallback failed: {fallback_error}"
        )
        raise compose_failure(primary_error, fallback_error, message) from primary_error


def compose_failure(
    primary_error: InferenceError, fallback_error: InferenceError, message: str
) -> InferenceError:
    """One error naming both failures; a timeout when both failures were timeouts."""
    if isinstance(primary_error, InferenceTimeout) and isinstance(fallback_error, InferenceTimeout):
        return InferenceTimeout(message)
    return InferenceError(message)
