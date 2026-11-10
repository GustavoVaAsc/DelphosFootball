"""Database repository queries for chat sessions and persisted exchanges.

Input: session_id, message contents, model_run_id, and pagination limits.
Output: Session rows and the saved exchange coordinates.
Responsibility: Parameterised reads and writes over app.chat_sessions and
app.chat_messages. Message rows carry explicit, distinct created_at timestamps
because CURRENT_TIMESTAMP is fixed per transaction and would order a user and
its assistant reply identically. The stored user message is capped at the
request contract's limit (schemas.chat.MAX_MESSAGE_CHARS), so a message that
reached the database is always bounded.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection

from delphos_backend.schemas.chat import MAX_MESSAGE_CHARS


async def get_session(conn: AsyncConnection, session_id: UUID) -> dict[str, Any] | None:
    """Fetch one chat session by primary key id, or None when it does not exist."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM app.chat_sessions
            WHERE id = %s;
            """,
            (session_id,),
        )
        return await cur.fetchone()


async def list_sessions(conn: AsyncConnection, limit: int = 50) -> list[dict[str, Any]]:
    """List chat sessions most-recently-active first."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM app.chat_sessions
            ORDER BY updated_at DESC, created_at DESC, id DESC
            LIMIT %s;
            """,
            (limit,),
        )
        return [dict(row) for row in await cur.fetchall()]


async def save_exchange(
    conn: AsyncConnection,
    session_id: UUID | None,
    user_content: str,
    assistant_content: str,
    model_run_id: str,
) -> dict[str, Any]:
    """Persist a complete exchange (user + assistant) in one commit.

    session_id=None creates the session first, titling it from the first user
    message truncated to 256 chars; an existing session gets its updated_at
    bumped. Called only after a successful turn, so a failed turn persists nothing.
    The stored user message is capped at MAX_MESSAGE_CHARS, the same bound the
    request schema enforces.
    """
    stamp = datetime.now(UTC)
    stored_user_content = user_content[:MAX_MESSAGE_CHARS]
    async with conn.cursor() as cur:
        if session_id is None:
            await cur.execute(
                "INSERT INTO app.chat_sessions (title) VALUES (%s) RETURNING id;",
                (stored_user_content.strip()[:256],),
            )
            row = await cur.fetchone()
            session_id = row["id"]
        else:
            await cur.execute(
                "UPDATE app.chat_sessions SET updated_at = %s WHERE id = %s;",
                (stamp, session_id),
            )
        await cur.execute(
            """
            INSERT INTO app.chat_messages (session_id, role, content, model_run_id, created_at)
            VALUES (%s, 'user', %s, %s, %s);
            """,
            (session_id, stored_user_content, model_run_id, stamp),
        )
        await cur.execute(
            """
            INSERT INTO app.chat_messages (session_id, role, content, model_run_id, created_at)
            VALUES (%s, 'assistant', %s, %s, %s)
            RETURNING created_at;
            """,
            (session_id, assistant_content, model_run_id, stamp + timedelta(microseconds=1)),
        )
        message_row = await cur.fetchone()
    await conn.commit()
    return {"session_id": session_id, "created_at": message_row["created_at"]}
