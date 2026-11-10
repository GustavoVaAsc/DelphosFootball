"""Unit tests for the chat persistence layer: bounded reads and capped writes."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from delphos_backend.repositories.chat import save_exchange
from delphos_backend.repositories.chat_messages import (
    count_messages,
    list_messages,
    list_recent_messages,
)
from delphos_backend.schemas.chat import MAX_MESSAGE_CHARS

SESSION_ID = uuid4()


def executed(mock_db: MagicMock) -> list[tuple[str, tuple]]:
    cursor = mock_db.cursor.return_value.__aenter__.return_value
    return [(str(call.args[0]), call.args[1]) for call in cursor.execute.call_args_list]


@pytest.mark.asyncio
async def test_save_exchange_caps_the_stored_user_message(mock_db: MagicMock) -> None:
    cursor = mock_db.cursor.return_value.__aenter__.return_value
    cursor.fetchone.side_effect = [{"id": uuid4()}, {"created_at": datetime.now(UTC)}]

    await save_exchange(mock_db, None, "x" * 5000, "respuesta", "run_test_001")

    user_params = next(
        params
        for sql, params in executed(mock_db)
        if "INSERT INTO app.chat_messages" in sql and "'user'" in sql
    )
    assert len(user_params[1]) == MAX_MESSAGE_CHARS


@pytest.mark.asyncio
async def test_list_messages_is_paginated(mock_db: MagicMock) -> None:
    await list_messages(mock_db, SESSION_ID, limit=10, offset=20)

    sql, params = executed(mock_db)[0]
    assert "LIMIT %s OFFSET %s" in sql
    assert params == (SESSION_ID, 10, 20)


@pytest.mark.asyncio
async def test_list_recent_messages_reads_only_the_tail(mock_db: MagicMock) -> None:
    await list_recent_messages(mock_db, SESSION_ID, limit=6)

    sql, params = executed(mock_db)[0]
    assert "ORDER BY created_at DESC" in sql
    assert "LIMIT %s" in sql
    assert params == (SESSION_ID, 6)


@pytest.mark.asyncio
async def test_count_messages_counts_the_session(mock_db: MagicMock) -> None:
    cursor = mock_db.cursor.return_value.__aenter__.return_value
    cursor.fetchone.return_value = {"total": 7}

    total = await count_messages(mock_db, SESSION_ID)

    assert total == 7
    sql, params = executed(mock_db)[0]
    assert "COUNT(*)" in sql
    assert params == (SESSION_ID,)
