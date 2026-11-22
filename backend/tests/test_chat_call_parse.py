"""Tests for reading a model reply as one or several tool calls."""

from __future__ import annotations

import pytest
from test_chat_tool_events import SEARCH

from delphos_backend.services.chat_call_parse import (
    INVALID_JSON,
    MAX_CALLS_PER_REPLY,
    MAX_TOOL_CALL_CHARS,
    MIXED_TEXT,
    NO_TOOL_KEY,
    TOO_MANY_CALLS,
    parse_tool_call,
    scan_calls,
)
from delphos_backend.services.chat_protocol import looks_like_tool_call

LEFT = (
    '{"tool": "search_players", "arguments": {"sub_position": "Left Winger", '
    '"valuation_status": "undervalued", "sort_by": "undervaluation", "limit": 10}}'
)
RIGHT = LEFT.replace("Left Winger", "Right Winger")
TWO_LINES = f"{LEFT}\n{RIGHT}"


def test_a_single_object_still_parses_to_one_call() -> None:
    assert scan_calls(SEARCH)[0] == [parse_tool_call(SEARCH)]
    assert scan_calls(SEARCH)[1] is None


@pytest.mark.parametrize(
    "reply",
    [
        TWO_LINES,
        f"{LEFT}{RIGHT}",
        f"  {LEFT}\n\n   {RIGHT}  \n",
        f"[{LEFT}, {RIGHT}]",
        f"[\n{LEFT},\n{RIGHT}\n]",
        f"```json\n{TWO_LINES}\n```",
        f"```\n[{LEFT},{RIGHT}]\n```",
        f"```json\n{TWO_LINES}",  # a truncated reply that lost only its closing fence
    ],
)
def test_every_multi_call_shape_parses_in_order(reply: str) -> None:
    calls, reason = scan_calls(reply)

    assert reason is None
    assert [call["arguments"]["sub_position"] for call in calls] == ["Left Winger", "Right Winger"]
    assert parse_tool_call(reply) is None  # not a lone call


@pytest.mark.parametrize(
    ("reply", "reason"),
    [
        (f"Voy a buscar ambos lados:\n{TWO_LINES}", MIXED_TEXT),
        (f"{LEFT}\nY ahora el otro lado.", MIXED_TEXT),
        (f"{LEFT}\nluego {RIGHT}", MIXED_TEXT),
        ("Claro, lo consulto.\n```json\n" + LEFT + "\n```", MIXED_TEXT),
        ("<tool_call>" + LEFT + "</tool_call>", MIXED_TEXT),
        (f"{LEFT}\n{RIGHT[:-20]}", INVALID_JSON),
        (LEFT[:-3], INVALID_JSON),
        ("{'tool': 'search_players'}", INVALID_JSON),
        (f"{LEFT},", INVALID_JSON),
        (f"{LEFT},\n{RIGHT}", INVALID_JSON),
        (f"{LEFT} )", INVALID_JSON),
        (f"```json\n{LEFT}\n```\n```json\n{RIGHT}\n```", INVALID_JSON),
        (f"{LEFT}\n" + '{"name": "search_players"}', NO_TOOL_KEY),
        ('{"otra": "clave"}', NO_TOOL_KEY),
        ("[]", NO_TOOL_KEY),
        ("   \n ", NO_TOOL_KEY),
        (f"[[{LEFT}]]", NO_TOOL_KEY),
        (f"[{LEFT}, 3]", NO_TOOL_KEY),
        (f'[{LEFT}, "texto"]', NO_TOOL_KEY),
        (f"{SEARCH}\n" * (MAX_CALLS_PER_REPLY + 1), TOO_MANY_CALLS),
        (f"[{','.join([SEARCH] * (MAX_CALLS_PER_REPLY + 1))}]", TOO_MANY_CALLS),
        (f"[{','.join([SEARCH] * MAX_CALLS_PER_REPLY)}, 3]", TOO_MANY_CALLS),  # the cap wins
    ],
)
def test_a_reply_that_is_not_only_calls_is_malformed(reply: str, reason: str) -> None:
    assert scan_calls(reply) == (None, reason)


@pytest.mark.parametrize("reply", ["3", "24 jugadores", "Hay 24 jugadores.", "NaN"])
def test_a_bare_scalar_or_a_sentence_stays_a_plain_answer(reply: str) -> None:
    calls, reason = scan_calls(reply)

    assert calls is None
    assert reason is not None
    assert not looks_like_tool_call(reply)


@pytest.mark.parametrize("constant", ["Infinity", "-Infinity", "NaN", "1e999", "-1e999"])
def test_non_finite_numbers_are_invalid_json(constant: str) -> None:
    reply = '{"tool": "search_players", "arguments": {"limit": ' + constant + "}}"

    assert scan_calls(reply) == (None, INVALID_JSON)
    assert looks_like_tool_call(reply)  # a broken call, never shown as an answer


def test_the_per_reply_cap_is_inclusive() -> None:
    calls, _ = scan_calls("\n".join([SEARCH] * MAX_CALLS_PER_REPLY))

    assert len(calls) == MAX_CALLS_PER_REPLY


def test_a_reply_over_the_size_bound_is_invalid_not_truncated() -> None:
    def named(size: int) -> str:
        return '{"tool": "search_players", "arguments": {"name": "' + "a" * size + '"}}'

    assert scan_calls(named(MAX_TOOL_CALL_CHARS - 100))[1] is None
    assert scan_calls(named(MAX_TOOL_CALL_CHARS)) == (None, INVALID_JSON)
    padded = SEARCH + "\n" + " " * 5000 + SEARCH  # the second call is never read half-way
    assert scan_calls(padded) == (None, INVALID_JSON)


def test_a_deeply_nested_payload_is_invalid_not_a_crash() -> None:
    assert scan_calls("[" * 3000 + "]" * 3000)[0] is None
