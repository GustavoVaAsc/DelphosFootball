"""The search_players chat tool reports each player's age in the active season."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from chat_fakes import simple_factory

from delphos_backend.services.chat_tools import execute_tool

RUN_ID = "run_test_001"


def search_row(**overrides: object) -> dict:
    row = {
        "player_id": 100,
        "name": "Lamine Yamal",
        "position": "Attack",
        "sub_position": "Right Winger",
        "club_name": "FC Barcelona",
        "market_value_eur": 180000000.0,
        "valuation_status": "fair",
        "cluster_id": 0,
        "age": 18.40613963039014,
    }
    row.update(overrides)
    return row


async def search(mock_db: MagicMock, rows: list[dict]) -> dict:
    with patch(
        "delphos_backend.services.chat_tool_queries.list_players",
        new=AsyncMock(return_value=(rows, len(rows))),
    ):
        return await execute_tool(simple_factory(mock_db), RUN_ID, "search_players", {})


@pytest.mark.asyncio
async def test_search_result_carries_the_season_age_rounded_to_one_decimal(
    mock_db: MagicMock,
) -> None:
    payload = await search(mock_db, [search_row()])

    assert payload["players"][0]["age"] == 18.4


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "row", [search_row(age=None), {k: v for k, v in search_row().items() if k != "age"}]
)
async def test_missing_age_is_null_not_a_crash(mock_db: MagicMock, row: dict) -> None:
    payload = await search(mock_db, [row])

    assert "error" not in payload
    assert payload["players"][0]["age"] is None
