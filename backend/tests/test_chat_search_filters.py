"""Tests for the list-valued sub_position and the age filters of search_players."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from chat_fakes import simple_factory
from httpx import AsyncClient
from test_player_sort_filter import page_query, stub_cursor

from delphos_backend.repositories.players import list_players
from delphos_backend.services.chat_tools import execute_tool

RUN_ID = "run_test_001"
TOOL = "delphos_backend.services.chat_tool_queries.list_players"


async def search(mock_db: MagicMock, arguments: dict) -> tuple[dict, AsyncMock]:
    with patch(TOOL, new=AsyncMock(return_value=([], 0))) as repo:
        payload = await execute_tool(simple_factory(mock_db), RUN_ID, "search_players", arguments)
    return payload, repo


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Left Winger", ["Left Winger"]),
        (["Left Winger"], ["Left Winger"]),
        (["Left Winger", "Right Winger"], ["Left Winger", "Right Winger"]),
        (["Right Winger", "Left Winger", "Right Winger"], ["Right Winger", "Left Winger"]),
        (["Left Winger", "Right Winger", "Centre-Back", "Left-Back"], None),
    ],
)
async def test_sub_position_accepts_one_value_or_a_list(
    mock_db: MagicMock, value: object, expected: list[str] | None
) -> None:
    payload, repo = await search(mock_db, {"sub_position": value})

    assert "error" not in payload
    assert repo.await_args.kwargs["sub_position"] == (expected or value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "value",
    [
        [],
        ["Left Winger", "Winger"],
        ["Left Winger", 3],
        ["Left Winger", None],
        ["Left Winger", "Right Winger", "Centre-Back", "Left-Back", "Right-Back"],
        {"Left Winger": 1},
        7,
    ],
)
async def test_an_invalid_sub_position_list_is_a_typed_error(
    mock_db: MagicMock, value: object
) -> None:
    payload, repo = await search(mock_db, {"sub_position": value})

    error = payload["error"]
    assert error["argument"] == "sub_position"
    assert "lista de 1 a 4 valores" in error["expected"]
    assert "Left Winger" in error["expected"]
    repo.assert_not_called()


@pytest.mark.asyncio
async def test_age_bounds_reach_the_repository(mock_db: MagicMock) -> None:
    payload, repo = await search(mock_db, {"min_age": 20, "max_age": 24})

    assert "error" not in payload
    assert repo.await_args.kwargs["min_age"] == 20
    assert repo.await_args.kwargs["max_age"] == 24


@pytest.mark.asyncio
async def test_age_bounds_default_to_unfiltered(mock_db: MagicMock) -> None:
    _, repo = await search(mock_db, {"min_age": None})

    assert repo.await_args.kwargs["min_age"] is None
    assert repo.await_args.kwargs["max_age"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("argument", ["min_age", "max_age"])
@pytest.mark.parametrize("value", [14, 46, 0, -3, 24.5, 24.0, "24", True, False, [24], {"a": 1}])
async def test_an_invalid_age_is_a_typed_error(
    mock_db: MagicMock, argument: str, value: object
) -> None:
    payload, repo = await search(mock_db, {argument: value})

    error = payload["error"]
    assert error["argument"] == argument
    assert error["message"] == f"argumento inválido: {argument}"
    assert "entero entre 15 y 45" in error["expected"]
    repo.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [15, 45])
async def test_the_age_range_is_inclusive(mock_db: MagicMock, value: int) -> None:
    payload, _ = await search(mock_db, {"min_age": value, "max_age": value})

    assert "error" not in payload


@pytest.mark.asyncio
async def test_an_inverted_age_range_is_a_typed_error(mock_db: MagicMock) -> None:
    payload, repo = await search(mock_db, {"min_age": 30, "max_age": 20})

    assert payload["error"]["argument"] == "min_age"
    assert "max_age" in payload["error"]["expected"]
    repo.assert_not_called()


@pytest.mark.asyncio
async def test_age_bounds_are_completed_years_as_bound_parameters(mock_db: MagicMock) -> None:
    sql, params = await page_query(mock_db, min_age=20, max_age=24)

    assert "s.age >= %s" in sql
    assert "s.age < %s" in sql
    assert "s.age <=" not in sql
    # 24 completed years means s.age below 25: a player aged 24.9 is still 24.
    assert params.index(20) < params.index(25)
    assert 24 not in params
    assert "20" not in sql
    assert "25" not in sql


@pytest.mark.asyncio
async def test_equal_bounds_select_every_player_of_that_age(mock_db: MagicMock) -> None:
    sql, params = await page_query(mock_db, min_age=21, max_age=21)

    assert "s.age >= %s" in sql
    assert "s.age < %s" in sql
    assert params[-4:-2] == [21, 22]  # 21.0 <= s.age < 22: the 21.x players


@pytest.mark.asyncio
async def test_a_single_age_bound_adds_one_condition(mock_db: MagicMock) -> None:
    sql, params = await page_query(mock_db, max_age=24)

    assert "s.age < %s" in sql
    assert "s.age >= %s" not in sql
    assert 25 in params

    sql, params = await page_query(mock_db, min_age=24)

    assert "s.age >= %s" in sql
    assert "s.age < %s" not in sql
    assert 24 in params


@pytest.mark.asyncio
async def test_several_sub_positions_are_one_bound_array(mock_db: MagicMock) -> None:
    sql, params = await page_query(mock_db, sub_position=["Left Winger", "Right Winger"])

    assert "p.sub_position = ANY(%s)" in sql
    assert ["Left Winger", "Right Winger"] in params
    assert "Winger" not in sql


@pytest.mark.asyncio
async def test_the_total_respects_the_age_and_sub_position_filters(mock_db: MagicMock) -> None:
    cur = stub_cursor(mock_db)

    await list_players(
        mock_db, RUN_ID, sub_position=["Left Winger", "Right Winger"], min_age=20, max_age=24
    )

    count_sql, count_params = cur.execute.await_args_list[0].args
    page_sql, page_params = cur.execute.await_args_list[-1].args
    assert "COUNT(*)" in count_sql
    for fragment in ("p.sub_position = ANY(%s)", "s.age >= %s", "s.age < %s"):
        assert fragment in count_sql
    assert ["Left Winger", "Right Winger"] in count_params
    assert 20 in count_params
    assert 25 in count_params
    assert page_params[:-2] == count_params  # the page adds only LIMIT and OFFSET


@pytest.mark.asyncio
async def test_without_age_or_list_the_query_is_unchanged(mock_db: MagicMock) -> None:
    sql, _ = await page_query(mock_db, sub_position="Left Winger")

    assert "p.sub_position = %s" in sql
    assert "s.age >=" not in sql
    assert "s.age <" not in sql
    assert "ANY(%s)" not in sql


@pytest.mark.asyncio
async def test_the_rest_listing_never_adds_the_chat_only_filters(
    client: AsyncClient, mock_db: MagicMock
) -> None:
    cur = stub_cursor(mock_db)
    cur.fetchone.side_effect = [{"model_run_id": RUN_ID, "dataset_version": 1}, {"total": 0}]

    response = await client.get("/players", params={"position": "Attack", "cluster_id": 1})

    assert response.status_code == 200
    statements = [call.args[0] for call in cur.execute.await_args_list]
    listing = [sql for sql in statements if "analytics.dim_players" in sql]
    assert len(listing) == 2  # the count and the page
    for sql in listing:
        assert "p.position = %s" in sql
        assert "cl.cluster_id = %s" in sql
        for absent in ("ANY(%s)", "s.age >=", "s.age <", "p.sub_position ="):
            assert absent not in sql
