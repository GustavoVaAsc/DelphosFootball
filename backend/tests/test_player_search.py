"""Unit tests for word-prefix player, club, and Spanish country search."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from delphos_backend.repositories.player_search import build_search_clause


def test_build_search_clause_uses_word_prefix_patterns_only() -> None:
    sql, params = build_search_clause("YAM")  # type: ignore[misc]
    assert "yam%" in params
    assert "% yam%" in params
    assert "%-yam%" in params
    assert "%'yam%" in params
    assert "%yam%" not in params
    assert "ILIKE" not in sql
    assert "ESCAPE '!'" in sql


def test_build_search_clause_maps_spanish_country_to_dataset_english() -> None:
    sql, params = build_search_clause("España")  # type: ignore[misc]
    assert "p.country_of_citizenship = ANY(%s)" in sql
    assert ["Spain"] in params


def test_build_search_clause_matches_multiword_spanish_country_and_club() -> None:
    _, us_params = build_search_clause("Estados Unidos")  # type: ignore[misc]
    assert ["United States"] in us_params

    club_sql, club_params = build_search_clause("Real Madrid")  # type: ignore[misc]
    assert "real%" in club_params
    assert "madrid%" in club_params
    assert " AND " in club_sql


def test_build_search_clause_returns_none_for_blank_query() -> None:
    assert build_search_clause(None) is None
    assert build_search_clause("   ") is None


@pytest.mark.asyncio
async def test_get_players_passes_word_prefix_search_to_sql(
    client: AsyncClient, mock_db: AsyncMock
) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cur.fetchone.side_effect = [
        {"model_run_id": "run_test_001", "dataset_version": 679, "activated_at": None},
        {"total": 0},
    ]
    cur.fetchall.return_value = []

    response = await client.get("/players?name=Real%20Esp")
    assert response.status_code == 200

    count_query, count_params = cur.execute.call_args_list[1].args
    assert "c.name" in count_query
    assert "p.country_of_citizenship" in count_query
    assert "% real%" in count_params
    assert ["Spain"] in count_params
