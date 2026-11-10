"""Pydantic request and response schemas for the conversational chat feature.

Input: JSON request payloads and chat rows from app.chat_sessions / app.chat_messages.
Output: Validated OpenAPI contracts for the /chat endpoints.
Responsibility: Defines the request shape (bounded message, optional session,
stream flag) and the response payloads for turns, sessions and history. The
message bound is owned here because it is the request contract; the repository
caps the stored copy at the same limit.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

MAX_MESSAGE_CHARS = 2000


class ChatRequest(BaseModel):
    """Request payload for POST /chat."""

    message: str = Field(
        min_length=1,
        max_length=MAX_MESSAGE_CHARS,
        description="Natural-language question from the client, at most 2000 characters",
    )
    session_id: UUID | None = Field(
        default=None, description="Existing session to continue; null starts a new session"
    )
    stream: bool = Field(default=False, description="Request a text/event-stream response")

    @field_validator("message")
    @classmethod
    def _message_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message must not be blank")
        return stripped


class ChatMessage(BaseModel):
    """One persisted exchange row from app.chat_messages."""

    id: UUID
    role: str
    content: str
    created_at: datetime


class ChatResponse(BaseModel):
    """Completed chat turn returned by POST /chat (non-streaming)."""

    session_id: UUID
    message: str
    model_run_id: str
    tools_called: list[str] = Field(default_factory=list)
    created_at: datetime


class ChatSession(BaseModel):
    """Session summary row from app.chat_sessions."""

    id: UUID
    title: str | None = None
    created_at: datetime
    updated_at: datetime


class ChatSessionListResponse(BaseModel):
    """Response payload for GET /chat/sessions, newest first."""

    items: list[ChatSession]
    total: int


class ChatHistoryResponse(BaseModel):
    """Response payload for GET /chat/sessions/{id}: one page of exchanges in order."""

    session_id: UUID
    title: str | None = None
    items: list[ChatMessage]
    total: int
    limit: int = 50
    offset: int = 0
