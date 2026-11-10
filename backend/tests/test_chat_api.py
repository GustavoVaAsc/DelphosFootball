"""Integration-style tests for the /chat routes with fake DB and fake inference."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from chat_fakes import TrackingConnectionFactory
from httpx import AsyncClient

from delphos_backend.api.chat import chat_connection_factory
from delphos_backend.main import app
from delphos_backend.services import chat_agent
from delphos_backend.services.llm_client import (
    CompletionResult,
    InferenceError,
    TokenUsage,
)

ACTIVE_RUN = {"model_run_id": "run_test_001", "dataset_version": 679, "activated_at": None}


def completion(content: str) -> CompletionResult:
    return CompletionResult(
        content=content,
        reasoning_content=None,
        usage=TokenUsage(),
        timings=None,
        model="test-model",
    )


def executed_sql(mock_db) -> list[str]:
    cursor = mock_db.cursor.return_value.__aenter__.return_value
    return [str(call.args[0]) for call in cursor.execute.call_args_list]


@pytest.fixture
def chat_factory(mock_db) -> TrackingConnectionFactory:
    """The connection factory the chat routes use, backed by the mocked connection."""
    return TrackingConnectionFactory(mock_db)


@pytest.fixture
async def chat_client(chat_factory: TrackingConnectionFactory, client: AsyncClient):
    """The API client with the chat connection factory bound to the mocked DB."""
    app.dependency_overrides[chat_connection_factory] = lambda: chat_factory
    yield client


@pytest.mark.asyncio
async def test_post_chat_returns_payload_and_persists_exchange(
    chat_client: AsyncClient, mock_db
) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    session_id = uuid4()
    created = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
    cur.fetchone.side_effect = [
        ACTIVE_RUN,
        {"id": session_id},
        {"created_at": created},
    ]

    answer = AsyncMock(return_value=completion("Respuesta con datos."))
    with patch.object(chat_agent, "chat_completion", new=answer):
        response = await chat_client.post("/chat", json={"message": "¿Delanteros infravalorados?"})

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == str(session_id)
    assert data["message"] == "Respuesta con datos."
    assert data["model_run_id"] == "run_test_001"
    assert data["tools_called"] == []
    assert data["created_at"].startswith("2026-11-08T12:00:00")
    mock_db.commit.assert_awaited_once()

    sql = executed_sql(mock_db)
    inserts = [q for q in sql if "INSERT INTO app.chat_messages" in q]
    assert len(inserts) == 2  # user row then assistant row
    user_params = next(
        call.args[1]
        for call in cur.execute.call_args_list
        if "INSERT INTO app.chat_messages" in str(call.args[0]) and "'user'" in str(call.args[0])
    )
    assert user_params[1] == "¿Delanteros infravalorados?"
    session_insert = next(q for q in sql if "INSERT INTO app.chat_sessions" in q)
    assert session_insert  # new session created as part of the exchange


@pytest.mark.asyncio
async def test_post_chat_title_derived_from_first_message_truncated_to_256(
    chat_client: AsyncClient, mock_db
) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    long_message = "Pregunta " + "x" * 400
    cur.fetchone.side_effect = [ACTIVE_RUN, {"id": uuid4()}, {"created_at": datetime.now(UTC)}]

    with patch.object(chat_agent, "chat_completion", new=AsyncMock(return_value=completion("ok"))):
        response = await chat_client.post("/chat", json={"message": long_message})

    assert response.status_code == 200
    session_call = next(
        call
        for call in cur.execute.call_args_list
        if "INSERT INTO app.chat_sessions" in str(call.args[0])
    )
    assert len(session_call.args[1][0]) == 256


@pytest.mark.asyncio
async def test_post_chat_rejects_an_oversized_message(chat_client: AsyncClient) -> None:
    response = await chat_client.post("/chat", json={"message": "x" * 2001})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_chat_does_not_hold_a_connection_while_the_model_thinks(
    chat_client: AsyncClient, chat_factory: TrackingConnectionFactory, mock_db
) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cur.fetchone.side_effect = [ACTIVE_RUN, {"id": uuid4()}, {"created_at": datetime.now(UTC)}]

    async def fake_completion(messages: list[dict], **kwargs: object) -> CompletionResult:
        assert chat_factory.active == 0, "a pooled connection is held during the LLM wait"
        await asyncio.sleep(0)
        return completion("Respuesta directa.")

    with patch.object(chat_agent, "chat_completion", new=fake_completion):
        response = await chat_client.post("/chat", json={"message": "hola"})

    assert response.status_code == 200
    assert chat_factory.active == 0


@pytest.mark.asyncio
async def test_post_chat_failed_turn_is_not_persisted(chat_client: AsyncClient, mock_db) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cur.fetchone.side_effect = [ACTIVE_RUN]

    with patch.object(
        chat_agent, "chat_completion", new=AsyncMock(side_effect=InferenceError("inference down"))
    ):
        response = await chat_client.post("/chat", json={"message": "hola"})

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    mock_db.commit.assert_not_awaited()
    assert not any("app.chat_messages" in q for q in executed_sql(mock_db))


@pytest.mark.asyncio
@pytest.mark.parametrize("message", ["", "   "])
async def test_post_chat_rejects_blank_message(
    chat_client: AsyncClient, mock_db, message: str
) -> None:
    response = await chat_client.post("/chat", json={"message": message})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_chat_unknown_session_returns_404(chat_client: AsyncClient, mock_db) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cur.fetchone.side_effect = [ACTIVE_RUN, None]

    response = await chat_client.post("/chat", json={"message": "hola", "session_id": str(uuid4())})

    assert response.status_code == 404
    assert response.json()["detail"] == "Chat session not found"


@pytest.mark.asyncio
async def test_post_chat_stream_emits_events_and_persists(
    chat_client: AsyncClient, mock_db
) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    session_id = uuid4()
    cur.fetchone.side_effect = [ACTIVE_RUN, {"id": session_id}, {"created_at": datetime.now(UTC)}]
    replies = [
        completion('{"tool": "search_players", "arguments": {"position": "Attack"}}'),
        completion("Tres resultados encontrados."),
    ]

    async def fake_completion(messages: list[dict], **kwargs: object) -> CompletionResult:
        return replies.pop(0)

    with (
        patch.object(chat_agent, "chat_completion", fake_completion),
        patch.object(
            chat_agent, "execute_tool", new=AsyncMock(return_value={"players": [], "total": 0})
        ),
    ):
        response = await chat_client.post(
            "/chat", json={"message": "busca atacantes", "stream": True}
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: tool" in body
    assert "event: message" in body
    assert "event: error" not in body
    assert '"search_players"' in body
    assert "Tres resultados encontrados." in body
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_post_chat_stream_tool_event_ships_a_summary_not_a_raw_row(
    chat_client: AsyncClient, mock_db
) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cur.fetchone.side_effect = [ACTIVE_RUN, {"id": uuid4()}, {"created_at": datetime.now(UTC)}]
    raw_profile = {
        "player_id": 100,
        "name": "Lionel Messi",
        "date_of_birth": "1987-06-24",
        "country_of_citizenship": "Argentina",
        "position": "Attack",
        "sub_position": "Right Winger",
        "club_name": "Inter Miami",
        "cluster_id": 0,
        "active_season": {"season": 2025, "goals": 20},
    }
    replies = [
        completion('{"tool": "get_player_profile", "arguments": {"player_id": 100}}'),
        completion("Su perfil está en los datos."),
    ]

    async def fake_completion(messages: list[dict], **kwargs: object) -> CompletionResult:
        return replies.pop(0)

    with (
        patch.object(chat_agent, "chat_completion", fake_completion),
        patch(
            "delphos_backend.services.chat_tool_players.get_player_profile",
            new=AsyncMock(return_value=raw_profile),
        ),
    ):
        response = await chat_client.post(
            "/chat", json={"message": "perfil de Messi", "stream": True}
        )

    assert response.status_code == 200
    body = response.text
    assert "date_of_birth" not in body
    assert "1987-06-24" not in body
    assert "country_of_citizenship" not in body
    assert "summary" in body
    assert "perfil" in body


@pytest.mark.asyncio
async def test_post_chat_stream_failure_before_first_byte_is_problem(
    chat_client: AsyncClient, mock_db
) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cur.fetchone.side_effect = [ACTIVE_RUN]

    with patch.object(
        chat_agent, "chat_completion", new=AsyncMock(side_effect=InferenceError("inference down"))
    ):
        response = await chat_client.post("/chat", json={"message": "hola", "stream": True})

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_post_chat_stream_midstream_failure_emits_error_event(
    chat_client: AsyncClient, mock_db
) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cur.fetchone.side_effect = [ACTIVE_RUN]
    with (
        patch.object(
            chat_agent,
            "chat_completion",
            new=AsyncMock(
                side_effect=[
                    completion('{"tool": "search_players", "arguments": {}}'),
                    InferenceError("inference down"),
                ]
            ),
        ),
        patch.object(
            chat_agent, "execute_tool", new=AsyncMock(return_value={"players": [], "total": 0})
        ),
    ):
        response = await chat_client.post("/chat", json={"message": "hola", "stream": True})

    assert response.status_code == 200
    assert "event: error" in response.text
    assert "event: message" not in response.text
    mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_chat_session_returns_exchanges_in_order(client: AsyncClient, mock_db) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    session_id = uuid4()
    first = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
    second = datetime(2026, 11, 8, 12, 0, 1, tzinfo=UTC)
    cur.fetchone.side_effect = [
        {
            "id": session_id,
            "title": "Consulta de plantilla",
            "created_at": first,
            "updated_at": second,
        },
        {"total": 2},
    ]
    cur.fetchall.return_value = [
        {
            "id": uuid4(),
            "session_id": session_id,
            "role": "user",
            "content": "Primera pregunta",
            "model_run_id": "run_test_001",
            "created_at": first,
        },
        {
            "id": uuid4(),
            "session_id": session_id,
            "role": "assistant",
            "content": "Primera respuesta",
            "model_run_id": "run_test_001",
            "created_at": second,
        },
    ]

    response = await client.get(f"/chat/sessions/{session_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == str(session_id)
    assert data["title"] == "Consulta de plantilla"
    assert [item["role"] for item in data["items"]] == ["user", "assistant"]
    assert [item["content"] for item in data["items"]] == ["Primera pregunta", "Primera respuesta"]
    assert data["total"] == 2
    assert data["limit"] == 50
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_get_chat_session_history_is_paginated(client: AsyncClient, mock_db) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    session_id = uuid4()
    cur.fetchone.side_effect = [{"id": session_id, "title": "T"}, {"total": 42}]
    cur.fetchall.return_value = []

    response = await client.get(f"/chat/sessions/{session_id}?limit=10&offset=20")

    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 10
    assert data["offset"] == 20
    assert data["total"] == 42
    page_query = next(
        call for call in cur.execute.call_args_list if "LIMIT %s OFFSET %s" in str(call.args[0])
    )
    assert page_query.args[1] == (session_id, 10, 20)


@pytest.mark.asyncio
async def test_get_chat_sessions_returns_newest_first(client: AsyncClient, mock_db) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    now = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)
    newer_id, older_id = uuid4(), uuid4()
    cur.fetchall.return_value = [
        {"id": newer_id, "title": "Nueva", "created_at": now, "updated_at": now},
        {"id": older_id, "title": "Vieja", "created_at": now, "updated_at": now},
    ]

    response = await client.get("/chat/sessions")

    assert response.status_code == 200
    data = response.json()
    assert [item["id"] for item in data["items"]] == [str(newer_id), str(older_id)]
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_get_chat_session_not_found(client: AsyncClient, mock_db) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cur.fetchone.return_value = None

    response = await client.get(f"/chat/sessions/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Chat session not found"
