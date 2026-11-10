"""Context budget for the chat agent: token estimate and history trimming.

Input: the question, the persisted history, and the active Settings.
Output: the prompt message list that fits the server context, plus the token
estimate used to trim it.
Responsibility: keep system + history + question + answer inside
settings.llm_context_size (LLM_PLAN §10.4). The budget is stated in tokens,
not exchanges, because Spanish prose costs ~11% more tokens per character on
the Qwen3.5 tokenizer (§7.6), so the estimate is chars/2.5 scaled by that
factor. History is dropped oldest-first and only on turn boundaries, so the
conversation never opens with an orphan assistant answer.
"""

from __future__ import annotations

from typing import Any

from delphos_backend.core.config import Settings
from delphos_backend.services.chat_prompt import SYSTEM_PROMPT

CHARS_PER_TOKEN = 2.5
SPANISH_TOKEN_FACTOR = 1.11
TOOL_RESULT_PREFIX = "Resultado de la herramienta «"
"""The marker of a tool-result message; the budget trim drops the oldest ones first."""


def estimate_tokens(text: str) -> int:
    """Estimate the tokens a Spanish-leaning text costs."""
    return int(len(text) / CHARS_PER_TOKEN * SPANISH_TOKEN_FACTOR) + 1


def context_budget(settings: Settings) -> int:
    """Tokens left for the prompt: the server context minus the answer cap."""
    return max(0, settings.llm_context_size - settings.llm_max_tokens)


def build_messages(
    question: str, history: list[dict[str, Any]], settings: Settings
) -> list[dict[str, Any]]:
    """Assemble system prompt + trimmed history + question within the budget."""
    budget = context_budget(settings)
    system = {"role": "system", "content": SYSTEM_PROMPT}
    question_message = {"role": "user", "content": question}
    recent = _turn_aligned(history, settings)
    while recent and _tokens(system, *recent, question_message) > budget:
        recent = _drop_oldest_turn(recent)
    if _tokens(system, *recent, question_message) > budget:
        # Only reachable with a context smaller than the prompt itself: shorten
        # the question so the invariant (total <= llm_context_size) always holds.
        spare = budget - estimate_tokens(SYSTEM_PROMPT)
        question_message = {"role": "user", "content": _fit_text(question, spare)}
    return [system, *recent, question_message]


def trim_to_budget(messages: list[dict[str, Any]], settings: Settings) -> list[dict[str, Any]]:
    """Trim a message list to the context budget, oldest first.

    The system prompt and the newest message are kept: the model needs the tool
    result it just asked for to answer. The tool loop calls this before every
    completion, because the tool payloads it appends are not part of the budget
    `build_messages` computed: without it, four tool results can push the
    request past the server's context size.

    The oldest tool result goes first (with the assistant call that produced it),
    then the oldest remaining message.
    """
    budget = context_budget(settings)
    trimmed = list(messages)
    while len(trimmed) > 2 and _tokens(*trimmed) > budget:
        index = _oldest_tool_result(trimmed)
        if index is None:
            trimmed.pop(1)
            continue
        trimmed.pop(index)
        if index > 1 and trimmed[index - 1].get("role") == "assistant":
            trimmed.pop(index - 1)
    if len(trimmed) == 2 and _tokens(*trimmed) > budget:
        # Even the newest message alone does not fit: shorten it.
        spare = budget - _tokens(trimmed[0])
        trimmed[1] = {
            **trimmed[1],
            "content": _fit_text(str(trimmed[1].get("content", "")), spare),
        }
    return trimmed


def _oldest_tool_result(messages: list[dict[str, Any]]) -> int | None:
    """The index of the oldest tool-result message, if the list holds one."""
    for index, message in enumerate(messages[1:], start=1):
        if str(message.get("content", "")).startswith(TOOL_RESULT_PREFIX):
            return index
    return None


def _turn_aligned(history: list[dict[str, Any]], settings: Settings) -> list[dict[str, Any]]:
    """The most recent exchanges, starting at a user turn."""
    keep = max(0, settings.llm_chat_history_turns) * 2
    recent = [m for m in history if m.get("role") in ("user", "assistant")]
    recent = recent[-keep:] if keep else []
    while recent and recent[0].get("role") != "user":
        recent.pop(0)
    return recent


def _drop_oldest_turn(recent: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop the oldest complete turn (a user message and its answer)."""
    end = len(recent)
    for index, message in enumerate(recent[1:], start=1):
        if message.get("role") == "user":
            end = index
            break
    return recent[end:]


def _tokens(*messages: dict[str, Any]) -> int:
    """Estimated tokens of a message list."""
    return sum(estimate_tokens(str(message.get("content", ""))) for message in messages)


def _fit_text(text: str, token_budget: int) -> str:
    """Shorten text so it fits the given token budget."""
    if token_budget <= 0:
        return ""
    max_chars = int(token_budget * CHARS_PER_TOKEN / SPANISH_TOKEN_FACTOR)
    return text[:max_chars]
