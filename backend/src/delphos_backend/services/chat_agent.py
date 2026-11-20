"""Tool loop for the conversational scouting agent.

Input: question, persisted history, active model_run_id, settings, and a
connection factory.
Output: ChatEvent stream ("tool_start" and "tool" progress, "message" final) or a
collected ChatTurn.
Responsibility: runs the capped tool loop (LLM_PLAN §10.3) through the shared
llm_client, bounds the concurrent LLM calls, parses the model's JSON tool calls,
describes each call before it runs, and feeds typed tool errors (including a
malformed call, never shown as an answer) back to the model. The prompt assembly
lives in chat_budget and the reply parsing in chat_protocol. May raise InferenceError;
callers map it to a problem response or an SSE error event.

The inference endpoint is decided once per turn, before the first answer of that
turn exists, and it is pinned for the whole turn: the tool results of the turn
never cross to the peer half-way through it, and one answer is never composed of
two models' output (ADR-033).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from delphos_backend.core.config import Settings
from delphos_backend.services.chat_budget import build_messages, trim_to_budget
from delphos_backend.services.chat_concurrency import llm_call_semaphore
from delphos_backend.services.chat_conn import ConnectionFactory
from delphos_backend.services.chat_prompt import FALLBACK_ANSWER
from delphos_backend.services.chat_protocol import (
    MALFORMED_CALL_ERROR,
    looks_like_tool_call,
    parse_tool_call,
    tool_result_message,
)
from delphos_backend.services.chat_tool_describe import describe_tool_call, remember_player_names
from delphos_backend.services.chat_tool_summary import summarize_tool_result
from delphos_backend.services.chat_tools import TOOL_NAMES, execute_tool
from delphos_backend.services.llm_client import (
    PRIMARY_ENDPOINT,
    InferenceError,
    chat_completion,
    resolve_target,
)

logger = logging.getLogger(__name__)

MAX_MALFORMED_RETRIES = 1
"""Broken tool calls the model may retry per turn, on top of the iteration cap."""


@dataclass(frozen=True)
class ChatEvent:
    """One unit of turn progress: "tool_start" and "tool" while working, "message" last."""

    type: str
    data: dict[str, Any]


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
        call = parse_tool_call(content)
        if call is None and not looks_like_tool_call(content):
            if not content:
                raise InferenceError("el modelo devolvió una respuesta vacía")
            yield ChatEvent("message", {"content": content, "tools_called": tools_called})
            return
        messages.append({"role": "assistant", "content": content})
        retry_spent = malformed >= MAX_MALFORMED_RETRIES or max_iterations == 0
        if (call is None and retry_spent) or (call is not None and step >= max_iterations):
            yield ChatEvent("message", {"content": FALLBACK_ANSWER, "tools_called": tools_called})
            return
        if call is None:
            # A broken call is retried like a bad argument; its text is never an answer.
            malformed += 1
            messages.append(tool_result_message("llamada", MALFORMED_CALL_ERROR))
            continue
        step += 1
        tool_name = call["tool"] if call["tool"] in TOOL_NAMES else "unknown"
        description = describe_tool_call(call["tool"], call.get("arguments"), names)
        yield ChatEvent("tool_start", {"step": step, "tool": tool_name, "description": description})
        payload = await execute_tool(conn_factory, run_id, call["tool"], call.get("arguments"))
        ok = "error" not in payload
        if ok:
            tools_called.append(tool_name)
            remember_player_names(payload, names)
        messages.append(tool_result_message(call["tool"], payload))
        yield ChatEvent(
            "tool",
            {
                "step": step,
                "tool": tool_name,
                "ok": ok,
                "summary": summarize_tool_result(call["tool"], payload),
                "description": description,
            },
        )
