"""Read endpoints for the chat sessions and their persisted exchanges.

Input: session path parameters and pagination query parameters.
Output: session list and session history payloads.
Responsibility: serve the two read-only chat views. The history endpoint is
paginated and every read is bounded, so a long session cannot pull an unbounded
result set out of app.chat_messages.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg import AsyncConnection

from delphos_backend.core.db import get_db
from delphos_backend.repositories.chat import get_session, list_sessions
from delphos_backend.repositories.chat_messages import count_messages, list_messages
from delphos_backend.schemas.chat import ChatHistoryResponse, ChatSessionListResponse

router = APIRouter(tags=["Chat"])


@router.get("/sessions", response_model=ChatSessionListResponse, summary="List chat sessions")
async def get_chat_sessions(
    conn: Annotated[AsyncConnection, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ChatSessionListResponse:
    """Return chat sessions most-recently-active first."""
    sessions = await list_sessions(conn, limit)
    return ChatSessionListResponse(items=sessions, total=len(sessions))


@router.get(
    "/sessions/{session_id}", response_model=ChatHistoryResponse, summary="Get session exchanges"
)
async def get_chat_session_history(
    session_id: UUID,
    conn: Annotated[AsyncConnection, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ChatHistoryResponse:
    """Return one page of a session's persisted exchanges in chronological order."""
    session = await get_session(conn, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found")
    messages = await list_messages(conn, session_id, limit=limit, offset=offset)
    total = await count_messages(conn, session_id)
    return ChatHistoryResponse(
        session_id=session["id"],
        title=session.get("title"),
        items=messages,
        total=total,
        limit=limit,
        offset=offset,
    )
