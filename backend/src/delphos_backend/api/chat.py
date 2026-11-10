"""API route handlers for the conversational chat feature (/chat).

Input: ChatRequest payloads.
Output: ChatResponse payloads and text/event-stream events.
Responsibility: resolves the active model run, runs the tool loop via chat_agent,
persists only complete exchanges, and maps inference failures to RFC 9457 problem
responses (before the first byte) or SSE error events (mid-stream), per LLM_PLAN §10.5.
No pooled connection is held while the model is thinking: every query opens its
own connection through the connection factory. The read-only session views live
in chat_sessions.py.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg import AsyncConnection

from delphos_backend.api.chat_sessions import router as sessions_router
from delphos_backend.api.chat_stream import start_chat_stream
from delphos_backend.core.config import Settings, get_settings
from delphos_backend.core.db import get_pool
from delphos_backend.repositories.active_run import get_active_model_run
from delphos_backend.repositories.chat import get_session, save_exchange
from delphos_backend.repositories.chat_messages import list_recent_messages
from delphos_backend.schemas.chat import ChatRequest, ChatResponse
from delphos_backend.services.chat_agent import run_chat_turn
from delphos_backend.services.chat_conn import ConnectionFactory
from delphos_backend.services.llm_client import InferenceError

router = APIRouter(prefix="/chat", tags=["Chat"])
router.include_router(sessions_router)


async def chat_connection_factory() -> AsyncGenerator[ConnectionFactory]:
    """Yield a factory that opens one pooled connection per use."""
    pool = get_pool()

    def factory() -> AbstractAsyncContextManager[AsyncConnection]:
        return pool.connection()

    yield factory


async def _resolve_active_run_id(conn: AsyncConnection) -> str:
    active_run = await get_active_model_run(conn)
    if not active_run:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No active model run published in database",
        )
    return active_run["model_run_id"]


async def _load_history(
    conn: AsyncConnection, session_id: UUID | None, settings: Settings
) -> list[dict]:
    """Load only the history tail the prompt may use."""
    if session_id is None:
        return []
    limit = max(0, settings.llm_chat_history_turns) * 2
    return await list_recent_messages(conn, session_id, limit=limit)


@router.post("", response_model=ChatResponse, summary="Ask a natural-language question")
async def chat(
    body: ChatRequest,
    conn_factory: Annotated[ConnectionFactory, Depends(chat_connection_factory)],
):
    """Answer one question with the capped tool loop; stream when requested."""
    settings = get_settings()
    async with conn_factory() as conn:
        run_id = await _resolve_active_run_id(conn)
        if body.session_id is not None and await get_session(conn, body.session_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found"
            )
        history = await _load_history(conn, body.session_id, settings)

    if body.stream:
        return await start_chat_stream(conn_factory, body, history, run_id)

    try:
        turn = await run_chat_turn(conn_factory, run_id, body.message, history, settings)
    except InferenceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat inference service unavailable",
        ) from exc
    async with conn_factory() as conn:
        saved = await save_exchange(conn, body.session_id, body.message, turn.answer, run_id)
    return ChatResponse(
        session_id=saved["session_id"],
        message=turn.answer,
        model_run_id=run_id,
        tools_called=turn.tools_called,
        created_at=saved["created_at"],
    )
