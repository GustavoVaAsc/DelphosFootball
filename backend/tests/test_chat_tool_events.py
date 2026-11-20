"""Tests for the tool_start/tool events and the rejection of malformed tool calls."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from chat_fakes import simple_factory
from test_chat_agent import RUN_ID, completion, make_settings

from delphos_backend.services import chat_agent
from delphos_backend.services.chat_agent import stream_chat_turn
from delphos_backend.services.chat_prompt import FALLBACK_ANSWER
from delphos_backend.services.chat_protocol import looks_like_tool_call, parse_tool_call
from delphos_backend.services.chat_turn import run_chat_turn

SEARCH = '{"tool": "search_players", "arguments": {"position": "Attack", "limit": 2}}'
PROFILE = '{"tool": "get_player_profile", "arguments": {"player_id": 7}}'
MALFORMED = [
    '{"tool": "search_players", "arguments": {"position": "Attack"',
    '{"tool": "search_players", "arguments": {position: Attack}}',
    '```json\n{"tool": "search_players", "arguments": {',
    '<tool_call>{"name": "search_players"}</tool_call>',
    'Voy a consultarlo: {"tool": "search_players", "arguments": {}',
    "{'tool': 'search_players'}",
    'Voy a buscar: {"name": "search_players", "arguments": {"position": "Attack"}}',
    'Claro, lo consulto.\n```json\n{"x": 1}\n```',
    '<|tool_call|>{"name": "x"}<|/tool_call|>',
    "Voy a usar get_cluster_summary ahora.",
    '{"otra": "clave"}',
]
LEGIT = [
    "El valor está en {valor} según la tabla.",
    'Dijo que el jugador "vale mucho" y cuesta {"{x}"} millones.',
    "Resultado: {nombre: Leão} aparece en el top 3 de extremos.",
]


def scripted(*replies: str):
    queue = list(replies)

    async def fake(messages: list[dict], **kwargs: object):
        fake.seen.append([m["content"] for m in messages])
        return completion(queue.pop(0))

    fake.seen = []
    return fake


async def collect(settings, *replies: str, payloads=None):
    execute = AsyncMock(side_effect=payloads or [{"players": [], "total": 0}] * 5)
    with (
        patch.object(chat_agent, "chat_completion", scripted(*replies)),
        patch.object(chat_agent, "execute_tool", execute),
    ):
        return [
            event
            async for event in stream_chat_turn(
                simple_factory(MagicMock()), RUN_ID, "¿Pregunta?", [], settings
            )
        ]


@pytest.mark.asyncio
async def test_tool_start_precedes_tool_with_matching_step_and_description() -> None:
    events = await collect(make_settings(), SEARCH, PROFILE, "Listo.")

    assert [e.type for e in events] == ["tool_start", "tool", "tool_start", "tool", "message"]
    first_start, first_tool, second_start, second_tool = (e.data for e in events[:4])
    assert first_start == {
        "step": 1,
        "tool": "search_players",
        "description": "Buscando jugadores en Ataque…",
    }
    assert set(first_tool) == {"step", "tool", "ok", "summary", "description"}
    assert first_tool["step"] == 1
    assert first_tool["description"] == first_start["description"]
    assert second_start["step"] == second_tool["step"] == 2
    assert second_start["description"] == "Consultando el perfil del jugador seleccionado…"


@pytest.mark.asyncio
async def test_tool_start_is_sent_before_the_tool_runs() -> None:
    order: list[str] = []

    async def execute(*args: object) -> dict:
        order.append("execute")
        return {"players": [], "total": 0}

    with (
        patch.object(chat_agent, "chat_completion", scripted(SEARCH, "Listo.")),
        patch.object(chat_agent, "execute_tool", execute),
    ):
        async for event in stream_chat_turn(
            simple_factory(MagicMock()), RUN_ID, "?", [], make_settings()
        ):
            order.append(event.type)

    assert order == ["tool_start", "execute", "tool", "message"]


@pytest.mark.asyncio
async def test_invalid_arguments_keep_the_typed_error_with_a_generic_description() -> None:
    bad = '{"tool": "get_player_profile", "arguments": {"player_id": "abc"}}'
    error = {"error": {"tool": "get_player_profile", "message": "argumento inválido: player_id"}}

    events = await collect(make_settings(), bad, "Listo.", payloads=[error])

    assert events[0].data["description"] == "Consultando los datos del modelo…"
    assert events[1].data["ok"] is False
    assert events[1].data["description"] == "Consultando los datos del modelo…"


@pytest.mark.asyncio
async def test_a_player_name_from_an_earlier_result_is_reused() -> None:
    found = {"players": [{"player_id": 7, "name": "Rafael Leão"}], "total": 1}
    profile = {"found": True, "profile": {"player_id": 7, "name": "Rafael Leão"}}

    events = await collect(make_settings(), SEARCH, PROFILE, "Listo.", payloads=[found, profile])

    assert events[2].data["description"] == "Consultando el perfil de Rafael Leão…"


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", MALFORMED)
async def test_malformed_call_is_retried_and_never_shown(bad: str) -> None:
    fake = scripted(bad, "Respuesta final.")
    with patch.object(chat_agent, "chat_completion", fake):
        turn = await run_chat_turn(simple_factory(MagicMock()), RUN_ID, "?", [], make_settings())

    assert turn.answer == "Respuesta final."
    assert turn.tools_called == []
    assert "mal formada" in fake.seen[1][-1]


@pytest.mark.asyncio
async def test_repeated_malformed_calls_end_in_the_fallback_answer() -> None:
    settings = make_settings(llm_max_tool_iterations=4)
    fake = scripted(*MALFORMED[:3])
    with patch.object(chat_agent, "chat_completion", fake):
        turn = await run_chat_turn(simple_factory(MagicMock()), RUN_ID, "?", [], settings)

    assert turn.answer == FALLBACK_ANSWER
    assert len(fake.seen) == 2  # one retry (MAX_MALFORMED_RETRIES), then the fallback


@pytest.mark.asyncio
async def test_a_zero_cap_answers_a_malformed_call_with_the_fallback() -> None:
    settings = make_settings(llm_max_tool_iterations=0)
    with patch.object(chat_agent, "chat_completion", scripted(MALFORMED[0])):
        turn = await run_chat_turn(simple_factory(MagicMock()), RUN_ID, "?", [], settings)

    assert turn.answer == FALLBACK_ANSWER


@pytest.mark.asyncio
@pytest.mark.parametrize("answer", LEGIT)
async def test_a_legitimate_answer_with_braces_or_quotes_passes_through(answer: str) -> None:
    assert parse_tool_call(answer) is None
    assert not looks_like_tool_call(answer)
    with patch.object(chat_agent, "chat_completion", scripted(answer)):
        turn = await run_chat_turn(simple_factory(MagicMock()), RUN_ID, "?", [], make_settings())

    assert turn.answer == answer


@pytest.mark.asyncio
async def test_valid_calls_after_a_malformed_retry_still_use_the_iteration_cap() -> None:
    fake = scripted(MALFORMED[0], SEARCH, PROFILE, "Listo.")
    with (
        patch.object(chat_agent, "chat_completion", fake),
        patch.object(chat_agent, "execute_tool", AsyncMock(return_value={"players": []})),
    ):
        turn = await run_chat_turn(simple_factory(MagicMock()), RUN_ID, "?", [], make_settings())

    assert turn.answer == "Listo."
    assert turn.tools_called == ["search_players", "get_player_profile"]


@pytest.mark.asyncio
async def test_an_unknown_tool_name_is_sent_to_the_client_as_unknown() -> None:
    hostile = '{"tool": "evil\\u202e{x}", "arguments": {}}'
    events = await collect(
        make_settings(), hostile, "Listo.", payloads=[{"error": {"message": "x"}}]
    )

    assert events[0].data["tool"] == "unknown"
    assert events[1].data["tool"] == "unknown"


@pytest.mark.asyncio
async def test_a_malformed_retry_does_not_consume_a_tool_execution() -> None:
    settings = make_settings(llm_max_tool_iterations=1)
    execute = AsyncMock(return_value={"players": [], "total": 0})
    with (
        patch.object(chat_agent, "chat_completion", scripted(MALFORMED[0], SEARCH, "Listo.")),
        patch.object(chat_agent, "execute_tool", execute),
    ):
        turn = await run_chat_turn(simple_factory(MagicMock()), RUN_ID, "?", [], settings)

    assert turn.answer == "Listo."
    assert turn.tools_called == ["search_players"]
    assert execute.await_count == 1


@pytest.mark.asyncio
async def test_the_tool_cap_still_holds_after_a_malformed_retry() -> None:
    settings = make_settings(llm_max_tool_iterations=1)
    execute = AsyncMock(return_value={"players": [], "total": 0})
    with (
        patch.object(chat_agent, "chat_completion", scripted(MALFORMED[0], SEARCH, SEARCH)),
        patch.object(chat_agent, "execute_tool", execute),
    ):
        turn = await run_chat_turn(simple_factory(MagicMock()), RUN_ID, "?", [], settings)

    assert turn.answer == FALLBACK_ANSWER
    assert execute.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "answer",
    [
        "El extremo tiene un valor de {38 M€} según el modelo y destaca entre sus pares.",
        'La etiqueta "infravalorado" aplica a este jugador.',
        "Puedes verlo así:\n```\nValor justo: 12 M€\nValor de mercado: 9 M€\n```",
    ],
)
async def test_spanish_answers_with_braces_quotes_or_a_plain_fence_pass_through(
    answer: str,
) -> None:
    assert not looks_like_tool_call(answer)
    with patch.object(chat_agent, "chat_completion", scripted(answer)):
        turn = await run_chat_turn(simple_factory(MagicMock()), RUN_ID, "?", [], make_settings())

    assert turn.answer == answer
