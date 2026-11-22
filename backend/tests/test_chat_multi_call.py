"""Tests for replies that carry several tool calls and the specific malformed-call errors."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from chat_fakes import simple_factory
from test_chat_agent import RUN_ID, make_settings
from test_chat_tool_events import PROFILE, SEARCH, collect, scripted

from delphos_backend.services import chat_agent
from delphos_backend.services.chat_budget import TOOL_RESULT_PREFIX, estimate_tokens, trim_to_budget
from delphos_backend.services.chat_call_parse import MAX_CALLS_PER_REPLY
from delphos_backend.services.chat_prompt import FALLBACK_ANSWER
from delphos_backend.services.chat_protocol import tool_result_block, tool_results_message
from delphos_backend.services.chat_turn import run_chat_turn

LEFT = (
    '{"tool": "search_players", "arguments": {"sub_position": "Left Winger", '
    '"valuation_status": "undervalued", "sort_by": "undervaluation", "limit": 10}}'
)
RIGHT = LEFT.replace("Left Winger", "Right Winger")
TWO_LINES = f"{LEFT}\n{RIGHT}"


@pytest.mark.asyncio
async def test_a_two_line_reply_runs_two_tools_and_ends_in_the_answer() -> None:
    execute = AsyncMock(
        side_effect=[
            {"players": [{"player_id": 1, "name": "Ala Uno"}], "total": 1},
            {"players": [{"player_id": 2, "name": "Ala Dos"}], "total": 1},
        ]
    )
    fake = scripted(TWO_LINES, "Hay dos extremos: Ala Uno y Ala Dos.")
    with (
        patch.object(chat_agent, "chat_completion", fake),
        patch.object(chat_agent, "execute_tool", execute),
    ):
        events = [
            event
            async for event in chat_agent.stream_chat_turn(
                simple_factory(MagicMock()), RUN_ID, "extremos", [], make_settings()
            )
        ]

    assert [event.type for event in events] == [
        "tool_start",
        "tool",
        "tool_start",
        "tool",
        "message",
    ]
    start1, tool1, start2, tool2 = (event.data for event in events[:4])
    assert (start1["step"], tool1["step"]) == (1, 1)
    assert (start2["step"], tool2["step"]) == (2, 2)
    assert start1["description"] == tool1["description"]
    assert start2["description"] == tool2["description"]
    assert "extremos izquierdos" in start1["description"]
    assert "extremos derechos" in start2["description"]
    assert tool1["ok"] and tool2["ok"]
    assert execute.await_count == 2
    final = events[-1].data
    assert final["content"] != FALLBACK_ANSWER
    assert final["tools_called"] == ["search_players", "search_players"]
    assert final["referenced_player_ids"] == [1, 2]
    # One assistant message, then ONE user message holding both results in call order.
    second_round = fake.seen[1]
    assert len(second_round) == 4  # system, question, assistant, merged results
    assert second_round[2] == TWO_LINES
    merged = second_round[3]
    assert merged.startswith(TOOL_RESULT_PREFIX)
    assert merged.count(TOOL_RESULT_PREFIX) == 2
    assert merged.index("Ala Uno") < merged.index("Ala Dos")


@pytest.mark.asyncio
async def test_mixed_tools_in_one_reply_feed_the_name_registry() -> None:
    found = {"players": [{"player_id": 7, "name": "Rafael Leão"}], "total": 1}
    profile = {"found": True, "profile": {"player_id": 7, "name": "Rafael Leão"}}

    events = await collect(
        make_settings(), f"{SEARCH}\n{PROFILE}", "Listo.", payloads=[found, profile]
    )

    assert events[2].data["description"] == "Consultando el perfil de Rafael Leão…"


@pytest.mark.asyncio
async def test_calls_over_the_remaining_budget_are_skipped_with_a_typed_error() -> None:
    settings = make_settings(llm_max_tool_iterations=2)
    execute = AsyncMock(return_value={"players": [], "total": 0})
    reply = "\n".join([SEARCH, PROFILE, SEARCH])
    fake = scripted(reply, "Respuesta con lo que hay.")
    with (
        patch.object(chat_agent, "chat_completion", fake),
        patch.object(chat_agent, "execute_tool", execute),
    ):
        events = [
            event
            async for event in chat_agent.stream_chat_turn(
                simple_factory(MagicMock()), RUN_ID, "?", [], settings
            )
        ]

    assert execute.await_count == 2
    assert [event.data["step"] for event in events if event.type == "tool"] == [1, 2]
    assert events[-1].data["content"] == "Respuesta con lo que hay."
    assert events[-1].data["tools_called"] == ["search_players", "get_player_profile"]
    assert len(fake.seen[1]) == 4  # system, question, assistant, one merged result message
    blocks = fake.seen[1][3].split("\n\n" + TOOL_RESULT_PREFIX)
    assert len(blocks) == 3
    assert "no se ejecutó" not in blocks[0] + blocks[1]
    skipped = json.loads(blocks[2].split("\n", 1)[1])["error"]
    assert skipped["message"].startswith("la llamada 3 de 3 no se ejecutó")
    assert skipped["tool"] == "search_players"


@pytest.mark.asyncio
async def test_a_reply_with_calls_after_the_budget_is_spent_ends_in_the_fallback() -> None:
    settings = make_settings(llm_max_tool_iterations=2)
    execute = AsyncMock(return_value={"players": [], "total": 0})
    with (
        patch.object(chat_agent, "chat_completion", scripted(TWO_LINES, TWO_LINES)),
        patch.object(chat_agent, "execute_tool", execute),
    ):
        turn = await run_chat_turn(simple_factory(MagicMock()), RUN_ID, "?", [], settings)

    assert turn.answer == FALLBACK_ANSWER
    assert execute.await_count == 2


@pytest.mark.asyncio
async def test_a_multi_call_reply_does_not_consume_the_malformed_retry() -> None:
    settings = make_settings(llm_max_tool_iterations=4)
    execute = AsyncMock(return_value={"players": [], "total": 0})
    fake = scripted('{"tool": "x"', TWO_LINES, "Listo.")
    with (
        patch.object(chat_agent, "chat_completion", fake),
        patch.object(chat_agent, "execute_tool", execute),
    ):
        turn = await run_chat_turn(simple_factory(MagicMock()), RUN_ID, "?", [], settings)

    assert turn.answer == "Listo."
    assert execute.await_count == 2


MARKER = "ZZ-MARCADOR-QUE-NO-DEBE-VOLVER"
RETRY_CASES = [
    ('{"tool": "search_players", "arguments": {"position": "Attack"', "inválido o está truncado"),
    (f"{LEFT}\n{RIGHT[:-20]}", "inválido o está truncado"),
    (f"{MARKER}: {LEFT}", "texto mezclado con la llamada"),
    (f"{LEFT}\n{MARKER}", "texto mezclado con la llamada"),
    (
        "\n".join([SEARCH] * 5),
        f"demasiadas llamadas en una respuesta (máximo {MAX_CALLS_PER_REPLY})",
    ),
    ('{"name": "search_players", "arguments": {}}', 'falta la clave "tool"'),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("bad", "detected"), RETRY_CASES)
async def test_each_malformed_case_gets_its_specific_retry_error(bad: str, detected: str) -> None:
    fake = scripted(bad, "Respuesta final.")
    with patch.object(chat_agent, "chat_completion", fake):
        turn = await run_chat_turn(simple_factory(MagicMock()), RUN_ID, "?", [], make_settings())

    assert turn.answer == "Respuesta final."
    retry = fake.seen[1][-1]
    error = json.loads(retry.split("\n", 1)[1])["error"]
    assert error["message"].startswith("llamada a herramienta mal formada")
    assert detected in error["message"]
    assert '{"tool": "<nombre>", "arguments": {...}}' in error["expected"]
    assert "un objeto JSON por línea" in error["expected"]
    assert MARKER not in retry  # the model's own text is never echoed back


@pytest.mark.asyncio
async def test_a_zero_cap_answers_a_multi_call_reply_with_the_fallback() -> None:
    settings = make_settings(llm_max_tool_iterations=0)
    execute = AsyncMock(return_value={"players": [], "total": 0})
    with (
        patch.object(chat_agent, "chat_completion", scripted(TWO_LINES)),
        patch.object(chat_agent, "execute_tool", execute),
    ):
        turn = await run_chat_turn(simple_factory(MagicMock()), RUN_ID, "?", [], settings)

    assert turn.answer == FALLBACK_ANSWER
    execute.assert_not_called()


@pytest.mark.asyncio
async def test_a_result_header_never_carries_the_models_raw_tool_name() -> None:
    hostile = '{"tool": "evil\\u202e{x}", "arguments": {}}'
    fake = scripted(f"{SEARCH}\n{hostile}\n{SEARCH}", "Listo.")
    with (
        patch.object(chat_agent, "chat_completion", fake),
        patch.object(
            chat_agent,
            "execute_tool",
            AsyncMock(
                side_effect=[
                    {"players": [], "total": 0},
                    {"error": {"tool": "unknown", "message": "herramienta desconocida"}},
                    {"players": [], "total": 0},
                ]
            ),
        ),
    ):
        await run_chat_turn(simple_factory(MagicMock()), RUN_ID, "?", [], make_settings())

    merged = fake.seen[1][3]
    assert "evil" not in merged
    assert "«unknown»" in merged


@pytest.mark.asyncio
async def test_an_unknown_tool_error_does_not_echo_the_models_name() -> None:
    from delphos_backend.services.chat_tools import execute_tool

    payload = await execute_tool(simple_factory(MagicMock()), RUN_ID, "evil{x}", {})

    assert payload["error"]["tool"] == "unknown"
    assert "evil" not in str(payload)


def test_trimming_drops_a_multi_call_reply_together_with_its_merged_results() -> None:
    settings = make_settings(llm_context_size=1024, llm_max_tokens=1)
    first = tool_results_message(
        [
            tool_result_block("search_players", {"rows": "a" * 800}),
            tool_result_block("search_players", {"rows": "b" * 800}),
        ]
    )
    newest = tool_result_block("get_player_profile", {"rows": "c" * 800})
    messages = [
        {"role": "system", "content": "sistema"},
        {"role": "user", "content": "pregunta"},
        {"role": "assistant", "content": TWO_LINES},
        first,
        {"role": "assistant", "content": PROFILE},
        {"role": "user", "content": newest},
    ]

    budget = settings.llm_context_size - settings.llm_max_tokens
    assert sum(estimate_tokens(m["content"]) for m in messages) > budget  # pressure

    trimmed = trim_to_budget(messages, settings)

    assert sum(estimate_tokens(m["content"]) for m in trimmed) <= budget

    assert trimmed == [messages[0], messages[1], messages[4], messages[5]]
    roles = [message["role"] for message in trimmed]
    assert roles == ["system", "user", "assistant", "user"]
