"""Unit tests for chat tool argument validation, result capping, and typed errors."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from chat_fakes import simple_factory

from delphos_backend.services.chat_tools import TOOL_NAMES, execute_tool

RUN_ID = "run_test_001"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("arguments", "bad_argument", "expected_fragment"),
    [
        ({"position": "Winger"}, "position", "Attack"),
        ({"valuation_status": "cheap"}, "valuation_status", "undervalued"),
        ({"cluster_id": 7}, "cluster_id", "0"),
        ({"cluster_id": "media"}, "cluster_id", "0"),
        ({"limit": 99}, "limit", "1"),
        ({"limit": "many"}, "limit", "1"),
    ],
)
async def test_search_players_rejects_bad_arguments(
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
@pytest.mark.parametrize("arguments", [{}, {"player_id": "abc"}, {"player_id": 1.5}])
async def test_player_tools_reject_bad_player_id(mock_db: MagicMock, arguments: dict) -> None:
    with patch(
        "delphos_backend.services.chat_tool_players.get_player_profile", new=AsyncMock()
    ) as repo:
        payload = await execute_tool(
            simple_factory(mock_db), RUN_ID, "get_player_profile", arguments
        )

    assert payload["error"]["argument"] == "player_id"
    repo.assert_not_called()


@pytest.mark.asyncio
async def test_integer_arguments_reject_booleans(mock_db: MagicMock) -> None:
    with patch(
        "delphos_backend.services.chat_tool_players.get_player_profile", new=AsyncMock()
    ) as repo:
        payload = await execute_tool(
            simple_factory(mock_db), RUN_ID, "get_player_profile", {"player_id": True}
        )

    assert payload["error"]["argument"] == "player_id"
    repo.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_tool_returns_typed_error_with_available_tools(
    mock_db: MagicMock,
) -> None:
    payload = await execute_tool(simple_factory(mock_db), RUN_ID, "drop_tables", {})

    assert payload["error"]["message"] == "herramienta desconocida"
    assert set(payload["error"]["available_tools"]) == set(TOOL_NAMES)


@pytest.mark.asyncio
async def test_unknown_player_returns_empty_result_not_error(mock_db: MagicMock) -> None:
    with patch(
        "delphos_backend.services.chat_tool_players.get_player_profile",
        new=AsyncMock(return_value=None),
    ):
        payload = await execute_tool(
            simple_factory(mock_db), RUN_ID, "get_player_profile", {"player_id": 999}
        )

    assert "error" not in payload
    assert payload == {"player_id": 999, "found": False, "profile": None}


@pytest.mark.asyncio
async def test_failing_tool_returns_typed_error_not_exception(mock_db: MagicMock) -> None:
    with patch(
        "delphos_backend.services.chat_tool_queries.list_players",
        new=AsyncMock(side_effect=RuntimeError("connection refused")),
    ):
        payload = await execute_tool(simple_factory(mock_db), RUN_ID, "search_players", {})

    assert payload["error"]["tool"] == "search_players"
    assert payload["error"]["message"] == "la herramienta falló al ejecutarse"


@pytest.mark.asyncio
async def test_search_players_caps_limit_and_labels_spanish(mock_db: MagicMock) -> None:
    row = {
        "player_id": 100,
        "name": "Lionel Messi",
        "position": "Attack",
        "sub_position": "Right Winger",
        "club_name": "Inter Miami",
        "market_value_eur": 25000000.0,
        "valuation_status": "undervalued",
        "cluster_id": 0,
        "image_url": "http://img.png",
    }
    with patch(
        "delphos_backend.services.chat_tool_queries.list_players",
        new=AsyncMock(return_value=([row], 1)),
    ) as repo:
        payload = await execute_tool(
            simple_factory(mock_db), RUN_ID, "search_players", {"limit": 7}
        )

    assert payload["total"] == 1
    assert payload["limit"] == 7
    assert payload["players"][0]["position_label"] == "Extremo Derecho"
    assert payload["players"][0]["valuation_label"] == "Infravalorado"
    assert "image_url" not in payload["players"][0]  # bounded row shape
    assert repo.await_args.kwargs["page_size"] == 7


@pytest.mark.asyncio
async def test_profile_tool_projects_an_allow_list(mock_db: MagicMock) -> None:
    raw_profile = {
        "player_id": 100,
        "name": "Lionel Messi",
        "position": "Attack",
        "sub_position": "Right Winger",
        "club_name": "Inter Miami",
        "cluster_id": 0,
        "date_of_birth": "1987-06-24",
        "country_of_citizenship": "Argentina",
        "foot": "left",
        "height_in_cm": 170,
        "player_code": "messi",
        "image_url": "http://img.png",
        "url": "https://www.transfermarkt.es/lionel-messi",
        "active_season": {"season": 2025, "goals": 20, "minutes": 3000, "age": 38},
    }
    with patch(
        "delphos_backend.services.chat_tool_players.get_player_profile",
        new=AsyncMock(return_value=raw_profile),
    ):
        payload = await execute_tool(
            simple_factory(mock_db), RUN_ID, "get_player_profile", {"player_id": 100}
        )

    profile = payload["profile"]
    assert profile["name"] == "Lionel Messi"
    assert profile["club_name"] == "Inter Miami"
    assert profile["position_label"] == "Extremo Derecho"
    assert profile["active_season"]["goals"] == 20
    for leaked in (
        "date_of_birth",
        "country_of_citizenship",
        "foot",
        "height_in_cm",
        "player_code",
        "image_url",
        "url",
    ):
        assert leaked not in profile


@pytest.mark.asyncio
async def test_valuation_tool_adds_spanish_label(mock_db: MagicMock) -> None:
    valuation = {
        "player_id": 100,
        "market_value_eur": 25000000.0,
        "fair_value_eur": 45000000.0,
        "valuation_status": "undervalued",
    }
    with patch(
        "delphos_backend.services.chat_tool_players.get_player_valuation",
        new=AsyncMock(return_value=valuation),
    ):
        payload = await execute_tool(
            simple_factory(mock_db), RUN_ID, "get_player_valuation", {"player_id": 100}
        )

    assert payload["found"] is True
    assert payload["valuation"]["valuation_label"] == "Infravalorado"


@pytest.mark.asyncio
async def test_replacements_tool_returns_the_capped_candidate_list(mock_db: MagicMock) -> None:
    repository_payload = {
        "target_player_id": 100,
        "target_name": "Lionel Messi",
        "qualifying_count": 7,
        "replacements": [
            {
                "rank": rank,
                "candidate_player_id": 200 + rank,
                "candidate_name": f"Candidato {rank}",
                "candidate_club_name": "Club",
                "similarity_score": 0.91,
                "candidate_market_value_eur": 1_000_000.0,
                "candidate_fair_value_eur": 1_200_000.0,
                "candidate_valuation_status": "undervalued",
                "cost_savings_eur": 100_000.0,
                "cost_ratio": 0.8,
                "candidate_image_url": "http://img.png",
                "candidate_country_of_citizenship": "Argentina",
            }
            for rank in range(1, 8)
        ],
    }
    with patch(
        "delphos_backend.services.chat_tool_players.get_player_replacements",
        new=AsyncMock(return_value=repository_payload),
    ):
        payload = await execute_tool(
            simple_factory(mock_db), RUN_ID, "get_player_replacements", {"player_id": 100}
        )

    assert payload["found"] is True
    assert len(payload["replacements"]) == 5
    assert payload["replacements"][0]["candidate_name"] == "Candidato 1"
    assert "candidates" not in payload
    assert "candidate_image_url" not in payload["replacements"][0]


@pytest.mark.asyncio
async def test_cluster_summary_filters_and_labels(mock_db: MagicMock) -> None:
    rows = [{"cluster_id": 0, "player_count": 10}, {"cluster_id": 1, "player_count": 20}]
    with patch(
        "delphos_backend.services.chat_tool_queries.get_clusters_summary",
        new=AsyncMock(return_value=rows),
    ):
        payload = await execute_tool(
            simple_factory(mock_db), RUN_ID, "get_cluster_summary", {"cluster_id": 1}
        )

    assert payload["total"] == 1
    assert payload["clusters"][0]["cluster_id"] == 1
    assert payload["clusters"][0]["cluster_label"] == "Box-to-Box"


@pytest.mark.asyncio
async def test_oversized_result_is_reported_as_an_error(mock_db: MagicMock) -> None:
    rows = [{"cluster_id": 0, "blob": "x" * 5000}]
    with patch(
        "delphos_backend.services.chat_tool_queries.get_clusters_summary",
        new=AsyncMock(return_value=rows),
    ):
        payload = await execute_tool(simple_factory(mock_db), RUN_ID, "get_cluster_summary", {})

    assert "error" in payload
    assert payload["error"]["truncated"] is True
    assert payload["error"]["tool"] == "get_cluster_summary"
    assert len(payload["error"]["preview"]) == 4000
