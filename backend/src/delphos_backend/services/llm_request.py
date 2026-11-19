"""One completion request: the endpoint it goes to, and the body it is written as.

Input: an endpoint target, the per-call options and the settings.
Output: the `InferenceTarget` of an endpoint, the `CallOptions` of a request and
the JSON body one completion request carries.
Responsibility: name what one request is. The body is the OpenAI-compatible
one the llama.cpp server expects, plus its llama.cpp extensions; the target
names the endpoint, its model id and its budget.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from delphos_backend.core.config import Settings


@dataclass(frozen=True)
class InferenceTarget:
    """One inference endpoint: which one it is, where it lives, and its budget."""

    kind: str
    base_url: str
    model_id: str
    timeout: float


@dataclass(frozen=True)
class CallOptions:
    """The per-call options one completion request carries."""

    messages: list[dict[str, Any]]
    max_tokens: int | None
    enable_thinking: bool | None
    seed: int | None
    response_format: dict[str, Any] | None


def build_body(target: InferenceTarget, options: CallOptions, cfg: Settings) -> dict[str, Any]:
    """The chat-completion request body for one endpoint."""
    thinking = options.enable_thinking
    if thinking is None:
        thinking = cfg.llm_enable_thinking
    body: dict[str, Any] = {
        "model": target.model_id,
        "messages": options.messages,
        "max_tokens": cfg.llm_max_tokens if options.max_tokens is None else options.max_tokens,
        "temperature": cfg.llm_temperature,
        "top_p": cfg.llm_top_p,
        "top_k": cfg.llm_top_k,  # llama.cpp extension; OpenAI has no top_k
        "presence_penalty": cfg.llm_presence_penalty,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": thinking},
    }
    if options.seed is not None:
        body["seed"] = options.seed
    if options.response_format is not None:
        body["response_format"] = options.response_format
    return body
