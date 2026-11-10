"""Unit tests for the chat tool loop, prompt, and context budget."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from chat_fakes import TrackingConnectionFactory, simple_factory

from delphos_backend.core.config import Settings
from delphos_backend.services import chat_agent
from delphos_backend.services.chat_agent import run_chat_turn, stream_chat_turn
from delphos_backend.services.chat_budget import build_messages, estimate_tokens
from delphos_backend.services.chat_prompt import FALLBACK_ANSWER, SYSTEM_PROMPT
from delphos_backend.services.chat_protocol import parse_tool_call
from delphos_backend.services.llm_client import (
    CompletionResult,
    InferenceError,
    TokenUsage,
)

RUN_ID = "run_test_001"
GROUNDING_RULE = (
    "Responde solo con datos de las herramientas. "
    "Si las herramientas no contienen la respuesta, dilo explícitamente."
)
TOOL_CALL_JSON = '{"tool": "search_players", "arguments": {"position": "Attack", "limit": 3}}'


def completion(content: str) -> CompletionResult:
    return CompletionResult(
        content=content,
        reasoning_content=None,
        usage=TokenUsage(),
        timings=None,
        model="test-model",
    )


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {"llm_max_tool_iterations": 4, "llm_chat_history_turns": 8}
    values.update(overrides)
    return Settings(**values)


def test_system_prompt_is_spanish_and_bans_ungrounded_answers() -> None:
    assert GROUNDING_RULE in SYSTEM_PROMPT
    assert "español" in SYSTEM_PROMPT
    for tool in (
        "search_players",
        "get_player_profile",
        "get_player_valuation",
        "get_player_replacements",
        "get_cluster_summary",
    ):
        assert tool in SYSTEM_PROMPT


def test_parse_tool_call_reads_json_reply() -> None:
    assert parse_tool_call(TOOL_CALL_JSON) == {
        "tool": "search_players",
        "arguments": {"position": "Attack", "limit": 3},
    }


def test_parse_tool_call_tolerates_markdown_fences() -> None:
    fenced = f"```json\n{TOOL_CALL_JSON}\n```"

    assert parse_tool_call(fenced)["tool"] == "search_players"


@pytest.mark.parametrize(
    "content",
    ["El delantero está infravalorado según los datos.", '{"otra": "clave"}', ""],
)
def test_parse_tool_call_replies_that_are_plain_answers(content: str) -> None:
    assert parse_tool_call(content) is None


def test_parse_tool_call_survives_a_deeply_nested_payload() -> None:
    nested = "[" * 50000 + "]" * 50000

    assert parse_tool_call(nested) is None


def test_context_budget_trims_history_to_chat_history_turns() -> None:
    settings = make_settings()
    history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg-{i}"} for i in range(30)
    ]

    messages = build_messages("¿Pregunta?", history, settings)

    assert messages[0]["role"] == "system"
    assert messages[-1] == {"role": "user", "content": "¿Pregunta?"}
    assert len(messages) == 1 + 2 * settings.llm_chat_history_turns + 1
    assert messages[1]["content"] == "msg-14"  # only the most recent exchanges survive


def test_long_history_is_trimmed_to_fit_the_context_budget() -> None:
    settings = make_settings(llm_context_size=2000)
    history = [
        {
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"mensaje {i} " + "x" * 200,
        }
        for i in range(40)
    ]

    messages = build_messages("¿Pregunta?", history, settings)

    spent = sum(estimate_tokens(message["content"]) for message in messages)
    assert spent + settings.llm_max_tokens <= settings.llm_context_size
    assert len(messages) < len(history) + 2  # the oldest exchanges were dropped
    assert messages[0]["role"] == "system"
    assert messages[-1] == {"role": "user", "content": "¿Pregunta?"}
    assert messages[1]["role"] == "user"  # the surviving history starts on a turn


def test_history_trim_never_opens_with_an_orphan_assistant_turn() -> None:
    settings = make_settings(llm_chat_history_turns=1)
    history = [
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u2"},
    ]

    messages = build_messages("q", history, settings)

    assert [message["content"] for message in messages[1:-1]] == ["u2"]


@pytest.mark.asyncio
async def test_loop_stops_after_four_tool_iterations() -> None:
    settings = make_settings()
    llm_calls: list[list[dict]] = []

    async def fake_completion(messages: list[dict], **kwargs: object) -> CompletionResult:
        llm_calls.append([dict(m) for m in messages])
        return completion(TOOL_CALL_JSON)

    execute = AsyncMock(return_value={"players": [], "total": 0})
    with (
        patch.object(chat_agent, "chat_completion", fake_completion),
        patch.object(chat_agent, "execute_tool", execute),
    ):
        events = [
            event
            async for event in stream_chat_turn(
                simple_factory(MagicMock()), RUN_ID, "q", [], settings
            )
        ]

    assert execute.await_count == 4  # the llm_max_tool_iterations cap
    assert len(llm_calls) == 5  # four tool rounds plus one forced final answer
    tool_events = [event for event in events if event.type == "tool"]
    assert len(tool_events) == 4
    assert events[-1].type == "message"
    assert events[-1].data["content"] == FALLBACK_ANSWER
    assert events[-1].data["tools_called"] == ["search_players"] * 4


@pytest.mark.asyncio
async def test_unknown_tool_returns_typed_error_to_the_model() -> None:
    settings = make_settings()
    replies = [completion('{"tool": "drop_tables", "arguments": {}}'), completion("Sin datos.")]
    captured: list[list[dict]] = []

    async def fake_completion(messages: list[dict], **kwargs: object) -> CompletionResult:
        captured.append([dict(m) for m in messages])
        return replies.pop(0)

    conn = MagicMock()
    with patch.object(chat_agent, "chat_completion", fake_completion):
        events = [
            event
            async for event in stream_chat_turn(simple_factory(conn), RUN_ID, "q", [], settings)
        ]

    tool_result = captured[1][-1]
    assert "herramienta desconocida" in tool_result["content"]
    assert "search_players" in tool_result["content"]
    assert events[0].data["ok"] is False
    assert events[-1].data["content"] == "Sin datos."
    assert events[-1].data["tools_called"] == []


@pytest.mark.asyncio
async def test_argument_validation_failure_names_the_argument() -> None:
    settings = make_settings()
    replies = [
        completion('{"tool": "search_players", "arguments": {"position": "Winger"}}'),
        completion("Corregido."),
    ]
    captured: list[list[dict]] = []

    async def fake_completion(messages: list[dict], **kwargs: object) -> CompletionResult:
        captured.append([dict(m) for m in messages])
        return replies.pop(0)

    with patch.object(chat_agent, "chat_completion", fake_completion):
        events = [
            event
            async for event in stream_chat_turn(
                simple_factory(MagicMock()), RUN_ID, "q", [], settings
            )
        ]

    tool_result = captured[1][-1]
    assert "argumento inválido: position" in tool_result["content"]
    assert events[0].data["ok"] is False
    assert events[-1].data["tools_called"] == []


@pytest.mark.asyncio
async def test_truncated_tool_result_is_reported_as_a_failure() -> None:
    settings = make_settings()
    replies = [
        completion('{"tool": "get_cluster_summary", "arguments": {}}'),
        completion("No puedo responder con datos."),
    ]

    async def fake_completion(messages: list[dict], **kwargs: object) -> CompletionResult:
        return replies.pop(0)

    with (
        patch.object(chat_agent, "chat_completion", fake_completion),
        patch(
            "delphos_backend.services.chat_tool_queries.get_clusters_summary",
            new=AsyncMock(return_value=[{"cluster_id": 0, "blob": "x" * 5000}]),
        ),
    ):
        events = [
            event
            async for event in stream_chat_turn(
                simple_factory(MagicMock()), RUN_ID, "q", [], settings
            )
        ]

    assert events[0].data["ok"] is False
    assert events[-1].data["tools_called"] == []


@pytest.mark.asyncio
async def test_no_pooled_connection_is_held_during_the_llm_wait() -> None:
    settings = make_settings()
    factory = TrackingConnectionFactory(MagicMock())
    replies = [completion(TOOL_CALL_JSON), completion("Sin datos.")]

    async def fake_completion(messages: list[dict], **kwargs: object) -> CompletionResult:
        assert factory.active == 0, "a pooled connection is held while the model thinks"
        await asyncio.sleep(0)
        return replies.pop(0)

    with (
        patch.object(chat_agent, "chat_completion", fake_completion),
        patch(
            "delphos_backend.services.chat_tool_queries.list_players",
            new=AsyncMock(return_value=([], 0)),
        ),
    ):
        events = [event async for event in stream_chat_turn(factory, RUN_ID, "q", [], settings)]

    assert factory.peak == 1  # one connection at a time, only around the tool call
    assert factory.active == 0
    assert events[-1].type == "message"


@pytest.mark.asyncio
async def test_concurrent_llm_calls_are_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DELPHOS_LLM_MAX_CONCURRENT_LLM_CALLS", "2")
    settings = make_settings()
    active = 0
    peak = 0

    async def fake_completion(messages: list[dict], **kwargs: object) -> CompletionResult:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return completion("Respuesta directa.")

    with patch.object(chat_agent, "chat_completion", fake_completion):
        await asyncio.gather(
            *(
                run_chat_turn(simple_factory(MagicMock()), RUN_ID, "¿Pregunta?", [], settings)
                for _ in range(6)
            )
        )

    assert peak <= 2


@pytest.mark.asyncio
async def test_plain_answer_is_one_call_with_no_tools() -> None:
    settings = make_settings()
    fake = AsyncMock(return_value=completion("Respuesta directa."))

    with patch.object(chat_agent, "chat_completion", fake):
        turn = await run_chat_turn(simple_factory(MagicMock()), RUN_ID, "¿Pregunta?", [], settings)

    assert turn.answer == "Respuesta directa."
    assert turn.tools_called == []
    assert fake.await_count == 1


@pytest.mark.asyncio
async def test_empty_answer_is_a_failed_turn() -> None:
    settings = make_settings()

    async def blank(messages: list[dict], **kwargs: object) -> CompletionResult:
        return completion("   ")

    with (
        patch.object(chat_agent, "chat_completion", blank),
        pytest.raises(InferenceError),
    ):
        await run_chat_turn(simple_factory(MagicMock()), RUN_ID, "¿Pregunta?", [], settings)


@pytest.mark.asyncio
@pytest.mark.parametrize("iterations", [0, -1])
async def test_a_non_positive_tool_cap_still_produces_one_answer(iterations: int) -> None:
    """A non-positive cap must still yield one answer, never an empty turn.

    The stub stands in for a misconfigured Settings: the field rejects
    negatives today, but the loop must not depend on that validation.
    """
    settings = SimpleNamespace(
        llm_max_tool_iterations=iterations,
        llm_chat_history_turns=8,
        llm_context_size=32768,
        llm_max_tokens=512,
    )
    fake = AsyncMock(return_value=completion("Respuesta directa."))

    with patch.object(chat_agent, "chat_completion", fake):
        turn = await run_chat_turn(simple_factory(MagicMock()), RUN_ID, "¿Pregunta?", [], settings)

    assert turn.answer == "Respuesta directa."
    assert fake.await_count == 1


@pytest.mark.asyncio
async def test_a_zero_tool_cap_answers_without_running_a_tool() -> None:
    """A cap of zero means no tool execution: the model is asked once."""
    settings = make_settings(llm_max_tool_iterations=0)
    fake = AsyncMock(return_value=completion(TOOL_CALL_JSON))
    execute = AsyncMock(return_value={"players": [], "total": 0})

    with (
        patch.object(chat_agent, "chat_completion", fake),
        patch.object(chat_agent, "execute_tool", execute),
    ):
        events = [
            event
            async for event in stream_chat_turn(
                simple_factory(MagicMock()), RUN_ID, "q", [], settings
            )
        ]

    assert execute.await_count == 0  # the tool was never run
    assert fake.await_count == 1  # the model was asked exactly once
    assert events[-1].type == "message"
    assert events[-1].data["content"] == FALLBACK_ANSWER
    assert events[-1].data["tools_called"] == []


@pytest.mark.asyncio
async def test_tool_payloads_never_exceed_the_context_budget() -> None:
    """The messages are re-trimmed before every completion, tool results included."""
    settings = make_settings(llm_context_size=4000)
    replies = [completion(TOOL_CALL_JSON), completion("Respuesta.")]
    captured: list[list[dict]] = []

    async def fake_completion(messages: list[dict], **kwargs: object) -> CompletionResult:
        captured.append([dict(m) for m in messages])
        return replies.pop(0)

    execute = AsyncMock(return_value={"blob": "x" * 8000})
    with (
        patch.object(chat_agent, "chat_completion", fake_completion),
        patch.object(chat_agent, "execute_tool", execute),
    ):
        events = [
            event
            async for event in stream_chat_turn(
                simple_factory(MagicMock()), RUN_ID, "q", [], settings
            )
        ]

    assert execute.await_count == 1
    spent = sum(estimate_tokens(message["content"]) for message in captured[-1])
    assert spent + settings.llm_max_tokens <= settings.llm_context_size
    assert events[-1].data["content"] == "Respuesta."


@pytest.mark.asyncio
async def test_inference_error_propagates_out_of_the_loop() -> None:
    settings = make_settings()

    async def failing(messages: list[dict], **kwargs: object) -> CompletionResult:
        raise InferenceError("inference down")

    with (
        patch.object(chat_agent, "chat_completion", failing),
        pytest.raises(InferenceError, match="inference down"),
    ):
        await run_chat_turn(simple_factory(MagicMock()), RUN_ID, "¿Pregunta?", [], settings)
