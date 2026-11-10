"""Database repository queries for the persisted chat messages.

Input: session_id plus a page window (limit, offset) or a tail size.
Output: chat_messages rows in chronological order, and the session's message count.
Responsibility: every read of app.chat_messages is bounded. The prompt reads
only the tail it needs (the most recent exchanges) and the history endpoint
reads one page, so a long session can neither blow the context budget nor pull
an unbounded result set.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg import AsyncConnection

MESSAGE_COLUMNS = "id, session_id, role, content, model_run_id, created_at"


async def list_messages(
    conn: AsyncConnection, session_id: UUID, *, limit: int = 50, offset: int = 0
) -> list[dict[str, Any]]:
    """List one page of a session's persisted exchanges in chronological order."""
    async with conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT {MESSAGE_COLUMNS}
            FROM app.chat_messages
            WHERE session_id = %s
            ORDER BY created_at ASC, id ASC
            LIMIT %s OFFSET %s;
            """,
            (session_id, limit, offset),
        )
        return [dict(row) for row in await cur.fetchall()]


async def list_recent_messages(
    conn: AsyncConnection, session_id: UUID, *, limit: int
) -> list[dict[str, Any]]:
    """List the most recent exchanges of a session, oldest first."""
    async with conn.cursor() as cur:
        await cur.execute(
            f"""
            SELECT {MESSAGE_COLUMNS}
            FROM app.chat_messages
            WHERE session_id = %s
            ORDER BY created_at DESC, id DESC
            LIMIT %s;
            """,
            (session_id, limit),
        )
        rows = [dict(row) for row in await cur.fetchall()]
    rows.reverse()
    return rows


async def count_messages(conn: AsyncConnection, session_id: UUID) -> int:
    """Count the persisted exchanges of a session."""
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT COUNT(*) AS total FROM app.chat_messages WHERE session_id = %s;",
            (session_id,),
        )
        row = await cur.fetchone()
    return int(row["total"]) if row else 0
