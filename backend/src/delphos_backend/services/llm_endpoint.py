"""One inference endpoint: its address, its budget, and the call that reaches it.

Input: an endpoint target, the per-call options, the settings and an optional transport.
Output: a CompletionResult.
Responsibility: build the /chat/completions body for one endpoint, post it, and map
every transport failure onto InferenceError. Which endpoint serves a call is the
client's decision (`llm_client`); this module only knows how to reach one.

Every failure of the call becomes an InferenceError, including a URL the HTTP
client cannot even parse: `httpx.InvalidURL` is not an `httpx.HTTPError`, so it
is mapped here explicitly. The report path must never raise (ADR-019).

The logs never carry the raw exception: `httpx.HTTPStatusError` renders the
full request URL, path and query, and an operator may put an API key in that
query. A log line names the endpoint as `scheme://host:port` and the exception
by its class name; the raised error carries the same two facts, so nothing
downstream can print the URL either.
"""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

import httpx

from delphos_backend.core.config import Settings
from delphos_backend.services.llm_protocol import (
    CompletionResult,
    InferenceError,
    InferenceTimeout,
    parse_completion,
)
from delphos_backend.services.llm_request import CallOptions, InferenceTarget, build_body

logger = logging.getLogger(__name__)


async def post_completion(
    target: InferenceTarget,
    options: CallOptions,
    cfg: Settings,
    transport: httpx.AsyncBaseTransport | None = None,
) -> CompletionResult:
    """Post one completion to one endpoint and parse the answer."""
    endpoint = f"{target.base_url.rstrip('/')}/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=target.timeout, transport=transport) as client:
            response = await client.post(endpoint, json=build_body(target, options, cfg))
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as exc:
        _log_failure(target, f"timed out after {target.timeout}s", exc)
        raise InferenceTimeout(f"LLM call timed out after {target.timeout}s") from exc
    except httpx.InvalidURL as exc:
        _log_failure(target, "used an invalid URL", exc)
        raise InferenceError(f"LLM call failed: the {target.kind} endpoint URL is invalid") from exc
    except httpx.HTTPError as exc:
        _log_failure(target, "failed", exc)
        raise InferenceError(
            f"LLM call failed: {type(exc).__name__} on {endpoint_label(target.base_url)}"
        ) from exc
    except ValueError as exc:  # httpx raises JSONDecodeError (a ValueError) on bad JSON
        _log_failure(target, "returned malformed JSON", exc)
        raise InferenceError(f"LLM returned malformed JSON: {type(exc).__name__}") from exc
    return parse_completion(
        data, target.model_id, endpoint=target.kind, requested_model=target.model_id
    )


def _log_failure(target: InferenceTarget, what: str, exc: Exception) -> None:
    """Log one failed call: the endpoint's label and the exception's class name.

    The raw exception is never logged: `httpx.HTTPStatusError` renders the
    full request URL, path and query, and an operator may put an API key in
    that query.
    """
    logger.warning(
        "LLM call to %s %s: %s", endpoint_label(target.base_url), what, type(exc).__name__
    )


def endpoint_label(base_url: str) -> str:
    """The endpoint's address without credentials or path: scheme://host:port.

    The label is what the logs name: a pasted URL may carry credentials, and a
    log line must not leak them or the prompt that travels with them.
    """
    try:
        parsed = urlsplit(base_url)
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        return "the configured endpoint"
    if not host:
        return "the configured endpoint"
    return f"{parsed.scheme or 'http'}://{host}{f':{port}' if port else ''}"
