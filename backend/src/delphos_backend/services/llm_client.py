"""Async OpenAI-compatible client for the local llama.cpp inference server.

Input: chat messages plus per-call sampling options (max_tokens, thinking, seed).
Output: CompletionResult with content, reasoning, usage and llama.cpp timings.
Responsibility: Builds the /chat/completions request and maps every failure mode
onto InferenceError (never fastapi.HTTPException), so callers can degrade to the
deterministic report with a 200 (LLM_PLAN §7.1). The exceptions and result
dataclasses are this module's single concept and would not justify files of their own.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from delphos_backend.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class InferenceError(Exception):
    """A local LLM call failed: transport, HTTP status, or malformed payload."""


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
    """One completed chat completion, typed for the report and chat paths."""

    content: str
    reasoning_content: str | None
    usage: TokenUsage
    timings: Timings | None
    model: str


async def chat_completion(
    messages: list[dict[str, Any]],
    *,
    settings: Settings | None = None,
    max_tokens: int | None = None,
    enable_thinking: bool | None = None,
    seed: int | None = None,
    response_format: dict[str, Any] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> CompletionResult:
    """Post one non-streaming chat completion; raise InferenceError on any failure.

    max_tokens defaults to Settings.llm_max_tokens (chat); the report path passes
    llm_report_max_tokens. enable_thinking defaults to Settings.llm_enable_thinking
    and is sent per request so report and chat can differ. seed and response_format
    are sent only when supplied. transport exists for tests (httpx.MockTransport).
    """
    cfg = settings or get_settings()
    endpoint = f"{cfg.llm_api_url.rstrip('/')}/chat/completions"
    thinking = cfg.llm_enable_thinking if enable_thinking is None else enable_thinking
    body: dict[str, Any] = {
        "model": cfg.llm_model_name,
        "messages": messages,
        "max_tokens": cfg.llm_max_tokens if max_tokens is None else max_tokens,
        "temperature": cfg.llm_temperature,
        "top_p": cfg.llm_top_p,
        "top_k": cfg.llm_top_k,  # llama.cpp extension; OpenAI has no top_k
        "presence_penalty": cfg.llm_presence_penalty,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": thinking},
    }
    if seed is not None:
        body["seed"] = seed
    if response_format is not None:
        body["response_format"] = response_format

    try:
        async with httpx.AsyncClient(
            timeout=cfg.llm_timeout_seconds, transport=transport
        ) as client:
            response = await client.post(endpoint, json=body)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as exc:
        logger.warning("Local LLM call timed out after %ss: %s", cfg.llm_timeout_seconds, exc)
        raise InferenceTimeout(f"LLM call timed out after {cfg.llm_timeout_seconds}s") from exc
    except httpx.HTTPError as exc:
        logger.warning("Local LLM call failed: %s", exc)
        raise InferenceError(f"LLM call failed: {exc}") from exc
    except ValueError as exc:  # httpx raises JSONDecodeError (a ValueError) on bad JSON
        logger.warning("Local LLM returned malformed JSON: %s", exc)
        raise InferenceError(f"LLM returned malformed JSON: {exc}") from exc
    return _parse_completion(data, cfg.llm_model_name)


def _parse_completion(data: Any, default_model: str) -> CompletionResult:
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
        usage = _parse_usage(data.get("usage"))
        timings = _parse_timings(data.get("timings"))
    except (TypeError, ValueError) as exc:
        raise InferenceError(f"LLM returned malformed usage or timings: {exc}") from exc
    return CompletionResult(
        content=content,
        reasoning_content=reasoning if isinstance(reasoning, str) else None,
        usage=usage,
        timings=timings,
        model=str(data.get("model") or default_model),
    )


def _parse_usage(raw: Any) -> TokenUsage:
    raw = raw or {}
    if not isinstance(raw, dict):
        raise ValueError(f"usage is {type(raw).__name__}, expected object")
    return TokenUsage(
        prompt_tokens=int(raw.get("prompt_tokens") or 0),
        completion_tokens=int(raw.get("completion_tokens") or 0),
        total_tokens=int(raw.get("total_tokens") or 0),
    )


def _parse_timings(raw: Any) -> Timings | None:
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
