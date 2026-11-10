"""Tool loop for the conversational scouting agent.

Input: question, persisted history, active model_run_id, settings, and a
connection factory.
Output: ChatEvent stream ("tool" progress, "message" final) or a collected ChatTurn.
Responsibility: runs the capped tool loop (LLM_PLAN §10.3) through the shared
llm_client, bounds the concurrent LLM calls, parses the model's JSON tool calls,
and feeds typed tool errors back to the model. The prompt assembly lives in
chat_budget and the reply parsing in chat_protocol. May raise InferenceError;
callers map it to a problem response or an SSE error event.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from delphos_backend.core.config import Settings
from delphos_backend.services.chat_budget import TOOL_RESULT_PREFIX, build_messages, trim_to_budget
from delphos_backend.services.chat_concurrency import llm_call_semaphore
from delphos_backend.services.chat_conn import ConnectionFactory
from delphos_backend.services.chat_prompt import FALLBACK_ANSWER
from delphos_backend.services.chat_protocol import parse_tool_call
from delphos_backend.services.chat_tool_summary import safe_tool_name, summarize_tool_result
from delphos_backend.services.chat_tools import execute_tool
from delphos_backend.services.llm_client import InferenceError, chat_completion


@dataclass(frozen=True)
class ChatEvent:
    """One unit of turn progress: "tool" while working, "message" for the answer."""

    type: str
    data: dict[str, Any]


@dataclass(frozen=True)
class ChatTurn:
    """A completed turn, as consumed by the non-streaming path."""

    answer: str
    tools_called: list[str]


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
    # Zero means "no tool execution at all": the model is asked once and a tool
    # call is answered with the fallback instead of being run.
    max_iterations = max(0, settings.llm_max_tool_iterations)
    for iteration in range(max_iterations + 1):
        # The tool payloads appended below are not in the budget build_messages
        # computed, so the messages are re-trimmed before every completion.
        messages = trim_to_budget(messages, settings)
        async with semaphore:
            result = await chat_completion(messages, settings=settings)
        content = result.content.strip()
        call = parse_tool_call(content)
        if call is None:
            if not content:
                raise InferenceError("el modelo devolvió una respuesta vacía")
            yield ChatEvent("message", {"content": content, "tools_called": tools_called})
            return
        messages.append({"role": "assistant", "content": content})
        if iteration >= max_iterations:
            yield ChatEvent("message", {"content": FALLBACK_ANSWER, "tools_called": tools_called})
            return
        payload = await execute_tool(conn_factory, run_id, call["tool"], call.get("arguments"))
        ok = "error" not in payload
        tool_name = safe_tool_name(call["tool"])
        if ok:
            tools_called.append(tool_name)
        serialized = json.dumps(payload, ensure_ascii=False, default=str)
        tool_result = f"{TOOL_RESULT_PREFIX}{call['tool']}»:\n{serialized}"
        messages.append({"role": "user", "content": tool_result})
        yield ChatEvent(
            "tool",
            {"tool": tool_name, "ok": ok, "summary": summarize_tool_result(call["tool"], payload)},
        )


async def run_chat_turn(
    conn_factory: ConnectionFactory,
    run_id: str,
    question: str,
    history: list[dict[str, Any]],
    settings: Settings,
) -> ChatTurn:
    """Consume the event stream to completion for the non-streaming path."""
    answer = ""
    tools_called: list[str] = []
    async for event in stream_chat_turn(conn_factory, run_id, question, history, settings):
        if event.type == "message":
            answer = event.data["content"]
            tools_called = event.data["tools_called"]
    if not answer:
        # An empty turn is a failure: it is never persisted as a successful exchange.
        raise InferenceError("el modelo no devolvió ninguna respuesta")
    return ChatTurn(answer=answer, tools_called=tools_called)
