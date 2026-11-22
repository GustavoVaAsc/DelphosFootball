"""Tool loop for the conversational scouting agent.

Input: question, persisted history, active model_run_id, settings, and a
connection factory.
Output: ChatEvent stream ("tool_start" and "tool" progress, "message" final) or a
collected ChatTurn.
Responsibility: runs the capped tool loop (LLM_PLAN §10.3) through the shared
llm_client, bounds the concurrent LLM calls, runs the one or several tool calls of
each reply, and feeds typed tool errors (including a malformed call, never shown as an
answer) back to the model. Prompt assembly lives in chat_budget, reply parsing in
chat_call_parse and the per-call execution in chat_call_run. May raise InferenceError;
callers map it to a problem response or an SSE error event.

The inference endpoint is decided once per turn, before the first answer of that
turn exists, and it is pinned for the whole turn: the tool results of the turn
never cross to the peer half-way through it, and one answer is never composed of
two models' output (ADR-033).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from delphos_backend.core.config import Settings
from delphos_backend.services.chat_budget import build_messages, trim_to_budget
from delphos_backend.services.chat_call_errors import malformed_call_error
from delphos_backend.services.chat_call_parse import scan_calls
from delphos_backend.services.chat_call_run import run_tool_call, skipped_call_block
from delphos_backend.services.chat_concurrency import llm_call_semaphore
from delphos_backend.services.chat_conn import ConnectionFactory
from delphos_backend.services.chat_event import ChatEvent
from delphos_backend.services.chat_player_refs import extract_referenced_player_ids
from delphos_backend.services.chat_prompt import FALLBACK_ANSWER
from delphos_backend.services.chat_protocol import (
    looks_like_tool_call,
    tool_result_message,
    tool_results_message,
)
from delphos_backend.services.chat_tools import execute_tool
from delphos_backend.services.llm_client import (
    PRIMARY_ENDPOINT,
    InferenceError,
    chat_completion,
    resolve_target,
)

logger = logging.getLogger(__name__)

MAX_MALFORMED_RETRIES = 1
"""Broken tool calls the model may retry per turn, on top of the iteration cap."""


def _message(content: str, tools_called: list[str], referenced_ids: list[int]) -> ChatEvent:
    """The final "message" event of a turn."""
    data = {"content": content, "tools_called": tools_called}
    return ChatEvent("message", {**data, "referenced_player_ids": referenced_ids})


async def stream_chat_turn(
    conn_factory: ConnectionFactory,
    run_id: str,
    question: str,
    history: list[dict[str, Any]],
    settings: Settings,
) -> AsyncIterator[ChatEvent]:
    """Run the capped tool loop, yielding progress events and the final message.

    At most llm_max_tool_iterations tool executions occur; a model that keeps
    calling tools gets FALLBACK_ANSWER instead of an unbounded loop (§10.3).
    The database connection is opened per tool execution, never across the LLM
    wait, and the LLM calls are bounded by a semaphore sized to the inference
    server's parallel slots.
    """
    messages = build_messages(question, history, settings)
    tools_called: list[str] = []
    semaphore = llm_call_semaphore(settings)
    # One endpoint for the whole turn: it is decided here, before the first
    # answer of the turn exists, and every call of the turn goes to it.
    target = await resolve_target(settings)
    # Zero means "no tool execution at all": the model is asked once and a tool
    # call is answered with the fallback instead of being run.
    max_iterations = max(0, settings.llm_max_tool_iterations)
    names: dict[int, str] = {}
    step = 0
    malformed = 0
    # Real executions are capped by max_iterations; malformed retries are extra completions.
    for _ in range(max_iterations + MAX_MALFORMED_RETRIES + 1):
        # The tool payloads appended below are not in the budget build_messages
        # computed, so the messages are re-trimmed before every completion.
        messages = trim_to_budget(messages, settings)
        async with semaphore:
            result = await chat_completion(messages, settings=settings, target=target)
        if result.endpoint != PRIMARY_ENDPOINT:
            logger.info("Chat turn served by the %s endpoint", result.endpoint)
        content = result.content.strip()
        calls, reason = scan_calls(content)
        if calls is None and not looks_like_tool_call(content):
            if not content:
                raise InferenceError("el modelo devolvió una respuesta vacía")
            referenced_player_ids = extract_referenced_player_ids(content, names)
            yield _message(content, tools_called, referenced_player_ids)
            return
        messages.append({"role": "assistant", "content": content})
        retry_spent = malformed >= MAX_MALFORMED_RETRIES or max_iterations == 0
        if (calls is None and retry_spent) or (calls is not None and step >= max_iterations):
            yield _message(FALLBACK_ANSWER, tools_called, [])
            return
        if calls is None:
            # A broken call is retried like a bad argument; its text is never an answer.
            malformed += 1
            messages.append(tool_result_message("llamada", malformed_call_error(reason)))
            continue
        # A reply's calls run in order, each with its own step and iteration; those over
        # the remaining budget get an error block. All blocks go in ONE user message, so
        # roles keep alternating and the budget trim never splits the group.
        room = max_iterations - step
        results: list[str] = []
        for call in calls[:room]:
            step += 1
            async for event in run_tool_call(
                conn_factory, run_id, call, step, results, names, tools_called, execute_tool
            ):
                yield event
        for ordinal, call in enumerate(calls[room:], start=room + 1):
            results.append(skipped_call_block(call, ordinal, len(calls)))
        messages.append(tool_results_message(results))
