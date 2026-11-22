"""Tests for the search ordering and sub-position filter of list_players and search_players."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from chat_fakes import simple_factory
from delphos_domain import SUB_POSITION_LABELS

from delphos_backend.repositories.player_order import PLAYER_ORDERINGS
from delphos_backend.repositories.players import list_players
from delphos_backend.services.chat_prompt import SYSTEM_PROMPT
from delphos_backend.services.chat_protocol import parse_tool_call
from delphos_backend.services.chat_tools import execute_tool

RUN_ID = "run_test_001"


def stub_cursor(mock_db: MagicMock) -> AsyncMock:
    """The cursor of a mock connection that finds no rows."""
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cur.fetchone.return_value = {"total": 0}
    cur.fetchall.return_value = []
    return cur


async def page_query(mock_db: MagicMock, **kwargs: object) -> tuple[str, list]:
    """The SQL and parameters of the page query (the last statement list_players runs)."""
    cur = stub_cursor(mock_db)
    await list_players(mock_db, RUN_ID, **kwargs)
    sql, params = cur.execute.await_args_list[-1].args
    return sql, params


@pytest.mark.asyncio
async def test_default_order_is_market_value_descending(mock_db: MagicMock) -> None:
    sql, _ = await page_query(mock_db)

    assert "ORDER BY pred.market_value_eur DESC NULLS LAST, p.name ASC, p.player_id ASC" in sql


@pytest.mark.asyncio
async def test_undervaluation_order_ranks_by_residual_descending(mock_db: MagicMock) -> None:
    sql, _ = await page_query(mock_db, sort_by="undervaluation")

    assert "ORDER BY pred.residual_log10 DESC NULLS LAST, p.name ASC, p.player_id ASC" in sql
    assert "market_value_eur DESC" not in sql


@pytest.mark.asyncio
async def test_unknown_order_never_reaches_the_sql(mock_db: MagicMock) -> None:
    cur = stub_cursor(mock_db)

    with pytest.raises(ValueError, match="sort_by"):
        await list_players(mock_db, RUN_ID, sort_by="1; DROP TABLE app.chat_messages")

    cur.execute.assert_not_called()


@pytest.mark.asyncio
async def test_sub_position_is_a_bound_parameter(mock_db: MagicMock) -> None:
    sql, params = await page_query(mock_db, sub_position="Left Winger")

    assert "p.sub_position = %s" in sql
    assert "Left Winger" in params
    assert "Left Winger" not in sql


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("arguments", "bad_argument", "expected_fragment"),
    [
        ({"sort_by": "cheapest"}, "sort_by", "undervaluation"),
        ({"sort_by": ""}, "sort_by", "overvaluation"),
        ({"sort_by": "residual_log10 DESC; --"}, "sort_by", "market_value"),
        ({"sort_by": 3}, "sort_by", "market_value"),
        ({"sort_by": ["undervaluation"]}, "sort_by", "market_value"),
        ({"sort_by": {"undervaluation": 1}}, "sort_by", "market_value"),
        ({"sort_by": "Undervaluation"}, "sort_by", "undervaluation"),
        ({"sort_by": "UNDERVALUATION"}, "sort_by", "undervaluation"),
        ({"sort_by": "undervalu\u0430tion"}, "sort_by", "undervaluation"),  # Cyrillic a
        ({"sort_by": "undervaluation "}, "sort_by", "undervaluation"),
        ({"sub_position": "Winger"}, "sub_position", "Left Winger"),
        ({"sub_position": "extremo"}, "sub_position", "Centre-Forward"),
        ({"sub_position": []}, "sub_position", "Left Winger"),
        ({"sub_position": ["Left Winger", "Winger"]}, "sub_position", "Left Winger"),
        ({"sub_position": ["Left Winger", 3]}, "sub_position", "Left Winger"),
        ({"sub_position": [["Left Winger"]]}, "sub_position", "Left Winger"),
        ({"sub_position": ["Left Winger", {"a": 1}]}, "sub_position", "Left Winger"),
        ({"sub_position": {"Left Winger": 1}}, "sub_position", "Left Winger"),
        ({"sub_position": "left winger"}, "sub_position", "Left Winger"),
        ({"sub_position": "LEFT WINGER"}, "sub_position", "Left Winger"),
        ({"sub_position": "Left W\u0456nger"}, "sub_position", "Left Winger"),  # Cyrillic i
        ({"sub_position": "Left Winger "}, "sub_position", "Left Winger"),
    ],
)
async def test_search_players_rejects_bad_sort_and_sub_position(
    mock_db: MagicMock, arguments: dict, bad_argument: str, expected_fragment: str
) -> None:
    with patch("delphos_backend.services.chat_tool_queries.list_players", new=AsyncMock()) as repo:
        payload = await execute_tool(simple_factory(mock_db), RUN_ID, "search_players", arguments)

    error = payload["error"]
    assert error["argument"] == bad_argument
    assert error["message"] == f"argumento inválido: {bad_argument}"
    assert expected_fragment in error["expected"]
    repo.assert_not_called()


@pytest.mark.asyncio
async def test_search_players_forwards_sort_and_sub_position(mock_db: MagicMock) -> None:
    with patch(
        "delphos_backend.services.chat_tool_queries.list_players",
        new=AsyncMock(return_value=([], 0)),
    ) as repo:
        await execute_tool(
            simple_factory(mock_db),
            RUN_ID,
            "search_players",
            {"sub_position": "Left Winger", "sort_by": "undervaluation", "limit": 3},
        )

    assert repo.await_args.kwargs["sub_position"] == ["Left Winger"]
    assert repo.await_args.kwargs["sort_by"] == "undervaluation"


@pytest.mark.asyncio
async def test_search_players_defaults_to_market_value_order(mock_db: MagicMock) -> None:
    with patch(
        "delphos_backend.services.chat_tool_queries.list_players",
        new=AsyncMock(return_value=([], 0)),
    ) as repo:
        payload = await execute_tool(simple_factory(mock_db), RUN_ID, "search_players", {})

    assert repo.await_args.kwargs["sort_by"] == "market_value"
    assert payload["sort_by"] == "market_value"


@pytest.mark.asyncio
async def test_overvaluation_order_ranks_by_residual_ascending(mock_db: MagicMock) -> None:
    sql, _ = await page_query(mock_db, sort_by="overvaluation")

    assert "ORDER BY pred.residual_log10 ASC NULLS LAST, p.name ASC, p.player_id ASC" in sql


def test_system_prompt_teaches_every_sort_and_sub_position_value() -> None:
    for value in (*PLAYER_ORDERINGS, *SUB_POSITION_LABELS):
        assert value in SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_system_prompt_example_is_a_valid_tool_call(mock_db: MagicMock) -> None:
    example = next(
        line.strip()
        for line in SYSTEM_PROMPT.splitlines()
        if line.strip().startswith('{"tool": "search_players", "arguments": {"sub_')
    )
    call = parse_tool_call(example)
    assert call is not None

    with patch(
        "delphos_backend.services.chat_tool_queries.list_players",
        new=AsyncMock(return_value=([], 0)),
    ) as repo:
        payload = await execute_tool(
            simple_factory(mock_db), RUN_ID, call["tool"], call["arguments"]
        )

    assert "error" not in payload
    assert repo.await_args.kwargs["sort_by"] == "undervaluation"
    assert repo.await_args.kwargs["sub_position"] == ["Left Winger"]


@pytest.mark.asyncio
async def test_system_prompt_list_example_is_a_valid_age_filtered_call(mock_db: MagicMock) -> None:
    example = next(
        line.strip()
        for line in SYSTEM_PROMPT.splitlines()
        if line.strip().startswith('{"tool"') and '"sub_position": ["' in line
    )
    call = parse_tool_call(example)
    assert call is not None

    with patch(
        "delphos_backend.services.chat_tool_queries.list_players",
        new=AsyncMock(return_value=([], 0)),
    ) as repo:
        payload = await execute_tool(
            simple_factory(mock_db), RUN_ID, call["tool"], call["arguments"]
        )

    assert "error" not in payload
    assert repo.await_args.kwargs["sub_position"] == ["Left Winger", "Right Winger"]
    assert repo.await_args.kwargs["max_age"] == 23
