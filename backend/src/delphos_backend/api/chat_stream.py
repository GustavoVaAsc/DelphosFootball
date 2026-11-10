"""SSE streaming response for the chat feature (LLM_PLAN §10.5).

Input: ChatRequest, persisted history, the active run id, and a connection factory.
Output: a text/event-stream StreamingResponse, or an RFC 9457 HTTPException when
the first turn step fails before any byte is sent.
Responsibility: starts the turn before headers so early failures stay ordinary
problem responses, persists only a completed exchange, and maps mid-stream
failures onto an `error` event once the 200 status is committed. The tool
progress event carries a summary sentence, never a serialized database row.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse

from delphos_backend.core.config import get_settings
from delphos_backend.repositories.chat import save_exchange
from delphos_backend.schemas.chat import ChatRequest
from delphos_backend.services.chat_agent import stream_chat_turn
from delphos_backend.services.chat_conn import ConnectionFactory
from delphos_backend.services.llm_client import InferenceError

logger = logging.getLogger(__name__)


def _sse(event_type: str, data: dict[str, Any]) -> str:
    """Frame one server-sent event; default=str covers UUID and datetime payloads."""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


async def start_chat_stream(
    conn_factory: ConnectionFactory,
    body: ChatRequest,
    history: list[dict[str, Any]],
    run_id: str,
) -> StreamingResponse:
    """Start the turn pre-response, then stream tool events and the final message."""
    events = stream_chat_turn(conn_factory, run_id, body.message, history, get_settings())
    try:
        first = await anext(events)  # a first-call failure happens before any byte
    except StopAsyncIteration as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat inference service produced no output",
        ) from exc
    except InferenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat inference service unavailable",
        ) from exc

    async def event_stream():
        current = first
        while True:
            try:
                if current.type == "tool":
                    yield _sse("tool", current.data)
                    current = await anext(events)
                    continue
                async with conn_factory() as conn:
                    saved = await save_exchange(
                        conn,
                        body.session_id,
                        body.message,
                        current.data["content"],
                        run_id,
                    )
                yield _sse(
                    "message",
                    {
                        "session_id": saved["session_id"],
                        "message": current.data["content"],
                        "model_run_id": run_id,
                        "tools_called": current.data["tools_called"],
                        "created_at": saved["created_at"],
                    },
                )
                return
            except StopAsyncIteration:
                yield _sse("error", {"detail": "el turno terminó sin respuesta"})
                return
            except Exception:
                logger.warning("Chat stream failed after headers were sent", exc_info=True)
                yield _sse("error", {"detail": "fallo del servicio de inferencia"})
                return

    return StreamingResponse(event_stream(), media_type="text/event-stream")
