"""Non-streaming chat turn: the collected answer of the tool loop.

Input: question, persisted history, active model_run_id, settings, and a
connection factory.
Output: a ChatTurn with the final answer and the tools that ran.
Responsibility: consume stream_chat_turn to completion for POST /chat without
stream. An empty turn is a failure, so it is never persisted. May raise
InferenceError; the caller maps it to a problem response.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from delphos_backend.core.config import Settings
from delphos_backend.services.chat_agent import stream_chat_turn
from delphos_backend.services.chat_conn import ConnectionFactory
from delphos_backend.services.llm_client import InferenceError


@dataclass(frozen=True)
class ChatTurn:
    """A completed turn, as consumed by the non-streaming path."""

    answer: str
    tools_called: list[str]


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
