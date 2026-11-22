"""Execution of one parsed tool call inside the chat loop.

Input: the call, its step number, and the per-turn registries.
Output: the "tool_start" and "tool" events of that call; its framed result is added to
the reply's result blocks and the result feeds the name registry and tools_called.
Responsibility: run exactly one call the way a lone call always ran, so a reply that
carries several calls is the same operation repeated in order. The loop joins the blocks
of one reply into a single message. The error block for a call the budget could not fit
lives here too, so the model knows it did not run. The tool name that reaches a result
header is always an allow-listed name or "unknown", never the model's raw text.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from delphos_backend.services.chat_conn import ConnectionFactory
from delphos_backend.services.chat_event import ChatEvent
from delphos_backend.services.chat_protocol import tool_result_block
from delphos_backend.services.chat_tool_describe import describe_tool_call, remember_player_names
from delphos_backend.services.chat_tool_summary import summarize_tool_result
from delphos_backend.services.chat_tools import TOOL_NAMES

ToolRunner = Callable[[ConnectionFactory, str, str, Any], Awaitable[dict[str, Any]]]


def tool_label(name: str) -> str:
    """The tool name when it is one of ours, "unknown" for anything the model invented."""
    return name if name in TOOL_NAMES else "unknown"


def skipped_call_block(call: dict[str, Any], ordinal: int, total: int) -> str:
    """The result block for call `ordinal` of `total`, not executed: the budget ran out."""
    label = tool_label(call["tool"])
    error = {
        "error": {
            "tool": label,
            "message": f"la llamada {ordinal} de {total} no se ejecutó: "
            "se agotó el límite de llamadas a herramientas",
            "expected": "responde ahora con los datos que ya tienes",
        }
    }
    return tool_result_block(label, error)


async def run_tool_call(
    conn_factory: ConnectionFactory,
    run_id: str,
    call: dict[str, Any],
    step: int,
    results: list[str],
    names: dict[int, str],
    tools_called: list[str],
    execute: ToolRunner,
) -> AsyncIterator[ChatEvent]:
    """Execute one call with `execute`, yielding its "tool_start" then "tool" event.

    The executor is a parameter so the loop owns the seam that tests replace.
    """
    tool_name = tool_label(call["tool"])
    description = describe_tool_call(call["tool"], call.get("arguments"), names)
    yield ChatEvent("tool_start", {"step": step, "tool": tool_name, "description": description})
    payload = await execute(conn_factory, run_id, call["tool"], call.get("arguments"))
    ok = "error" not in payload
    if ok:
        tools_called.append(tool_name)
        remember_player_names(payload, names)
    results.append(tool_result_block(tool_name, payload))
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
