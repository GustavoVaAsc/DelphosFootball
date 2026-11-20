"""The wire protocol of the OpenAI-compatible inference API.

Input: a decoded chat-completion response body.
Output: a `CompletionResult` (content, reasoning, usage, timings, provenance), or an
`InferenceError` when the body does not answer the protocol.
Responsibility: name the errors an inference call raises and turn a response body
into a typed result. The exceptions and the result dataclasses are this module's
single concept and would not justify files of their own; `llm_client` re-exports
them, so the callers keep one import path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PRIMARY_ENDPOINT = "primary"
"""The endpoint the backend is configured to use first."""

FALLBACK_ENDPOINT = "fallback"
"""The second endpoint, reached over ZeroTier, used when the primary is unusable."""


class InferenceError(Exception):
    """An LLM call failed: transport, HTTP status, or malformed payload."""


class InferenceTimeout(InferenceError):
    """The call timed out; the caller falls back without attempting a repair."""


@dataclass(frozen=True)
class TokenUsage:
    """Token counts reported by the server."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True)
class Timings:
    """llama.cpp `timings` object: prefill and decode throughput."""

    prompt_n: int = 0
    predicted_n: int = 0
    prompt_per_second: float = 0.0
    predicted_per_second: float = 0.0


@dataclass(frozen=True)
class CompletionResult:
    """One completed chat completion, typed for the report and chat paths.

    `model` is the id the server reported; `requested_model` is the id the
    backend asked for, which is the one the report cache keys on. `endpoint`
    names the endpoint that served the call.
    """

    content: str
    reasoning_content: str | None
    usage: TokenUsage
    timings: Timings | None
    model: str
    endpoint: str = PRIMARY_ENDPOINT
    requested_model: str = ""


def parse_completion(
    data: Any,
    default_model: str,
    *,
    endpoint: str = PRIMARY_ENDPOINT,
    requested_model: str = "",
) -> CompletionResult:
    """Turn a decoded response body into CompletionResult or raise InferenceError."""
    if not isinstance(data, dict):
        raise InferenceError(f"unexpected LLM response type: {type(data).__name__}")
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise InferenceError("LLM response contained no choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise InferenceError("LLM response contained a malformed choice")
    message = first.get("message") or {}
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise InferenceError("LLM returned an empty completion")
    reasoning = message.get("reasoning_content")
    try:
        usage = parse_usage(data.get("usage"))
        timings = parse_timings(data.get("timings"))
    except (TypeError, ValueError) as exc:
        raise InferenceError(f"LLM returned malformed usage or timings: {exc}") from exc
    return CompletionResult(
        content=content,
        reasoning_content=reasoning if isinstance(reasoning, str) else None,
        usage=usage,
        timings=timings,
        model=str(data.get("model") or default_model),
        endpoint=endpoint,
        requested_model=requested_model,
    )


def parse_usage(raw: Any) -> TokenUsage:
    """Turn the server's `usage` object into TokenUsage or raise ValueError."""
    raw = raw or {}
    if not isinstance(raw, dict):
        raise ValueError(f"usage is {type(raw).__name__}, expected object")
    return TokenUsage(
        prompt_tokens=int(raw.get("prompt_tokens") or 0),
        completion_tokens=int(raw.get("completion_tokens") or 0),
        total_tokens=int(raw.get("total_tokens") or 0),
    )


def parse_timings(raw: Any) -> Timings | None:
    """Turn the server's `timings` object into Timings, or raise ValueError."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"timings is {type(raw).__name__}, expected object")
    return Timings(
        prompt_n=int(raw.get("prompt_n") or 0),
        predicted_n=int(raw.get("predicted_n") or 0),
        prompt_per_second=float(raw.get("prompt_per_second") or 0.0),
        predicted_per_second=float(raw.get("predicted_per_second") or 0.0),
    )
