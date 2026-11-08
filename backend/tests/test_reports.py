"""Unit tests for AI scouting report generation and retrieval routes (/reports)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException, status
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_generate_report_returns_cached_when_available(
    client: AsyncClient, mock_db: AsyncMock
) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cur.fetchone.side_effect = [
        {"model_run_id": "run_test_001", "dataset_version": 679, "activated_at": None},
        {
            "id": 7,
            "player_id": 100,
            "player_name": "Lionel Messi",
            "model_run_id": "run_test_001",
            "report_type": "scouting",
            "content": "Cached scouting report for Lionel Messi.",
            "created_at": datetime(2026, 11, 7, 12, 0, tzinfo=UTC),
        },
    ]

    response = await client.post("/reports/generate", json={"player_id": 100})
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 7
    assert data["player_name"] == "Lionel Messi"
    assert data["content"] == "Cached scouting report for Lionel Messi."


@pytest.mark.asyncio
async def test_generate_report_calls_llm_and_persists(
    client: AsyncClient, mock_db: AsyncMock
) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    # 1. active run
    # 2. cached report -> None
    # 3. get_player_profile
    # 4. get_player_valuation
    # 5. get_player_replacements (target)
    # 6. save_report INSERT RETURNING
    cur.fetchone.side_effect = [
        {"model_run_id": "run_test_001", "dataset_version": 679, "activated_at": None},
        None,
        {
            "model_run_id": "run_test_001",
            "player_id": 100,
            "name": "Lionel Messi",
            "first_name": "Lionel",
            "last_name": "Messi",
            "player_code": "lionel-messi",
            "country_of_citizenship": "Argentina",
            "date_of_birth": "1987-06-24",
            "position": "Attack",
            "sub_position": "Right Winger",
            "foot": "left",
            "height_in_cm": 170,
            "club_id": 1,
            "club_name": "Inter Miami",
            "image_url": "http://img.png",
            "url": "http://tm.de/messi",
            "cluster_id": 0,
            "season": 2025,
            "as_of_date": "2025-06-01",
            "league_id": "ES1",
            "minutes": 1800.0,
            "apps": 20.0,
            "starts": 20.0,
            "goals": 15.0,
            "assists": 12.0,
            "yellow_cards": 1.0,
            "red_cards": 0.0,
            "starter_ratio": 1.0,
            "win_rate": 0.75,
            "clean_sheet_rate": 0.3,
            "goals_conceded_per_match": 1.0,
            "league_position": 1.0,
            "age": 37.0,
        },
        {
            "player_id": 100,
            "name": "Lionel Messi",
            "model_run_id": "run_test_001",
            "season": 2025,
            "market_value_eur": 25000000.0,
            "fair_value_eur": 45000000.0,
            "residual_log10": 0.255,
            "valuation_status": "undervalued",
            "is_undervalued": True,
            "rf_undervalued_prob": 0.82,
            "dt_undervalued_pred": True,
            "rf_undervalued_pred": True,
        },
        {
            "target_player_id": 100,
            "target_name": "Lionel Messi",
            "model_run_id": "run_test_001",
            "season": 2025,
            "is_elite_asset": True,
            "target_market_value_eur": 25000000.0,
            "qualifying_count": 0,
            "shortfall_reason": "no_peer_below_cost_ceiling",
        },
        {
            "id": 8,
            "player_id": 100,
            "model_run_id": "run_test_001",
            "report_type": "scouting",
            "content": "Generated executive scouting report.",
            "created_at": datetime(2026, 11, 7, 12, 5, tzinfo=UTC),
        },
    ]
    cur.fetchall.return_value = []

    with patch(
        "delphos_backend.api.reports.generate_llm_report_text",
        new=AsyncMock(return_value="Generated executive scouting report."),
    ):
        response = await client.post("/reports/generate", json={"player_id": 100})

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 8
    assert data["player_name"] == "Lionel Messi"
    assert data["content"] == "Generated executive scouting report."
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_report_llm_unavailable_returns_503_problem(
    client: AsyncClient, mock_db: AsyncMock
) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cur.fetchone.side_effect = [
        {"model_run_id": "run_test_001", "dataset_version": 679, "activated_at": None},
        None,
        {
            "model_run_id": "run_test_001",
            "player_id": 100,
            "name": "Lionel Messi",
            "first_name": "Lionel",
            "last_name": "Messi",
            "player_code": "lionel-messi",
            "country_of_citizenship": "Argentina",
            "date_of_birth": "1987-06-24",
            "position": "Attack",
            "sub_position": "Right Winger",
            "foot": "left",
            "height_in_cm": 170,
            "club_id": 1,
            "club_name": "Inter Miami",
            "image_url": "http://img.png",
            "url": "http://tm.de/messi",
            "cluster_id": 0,
            "season": None,
        },
        {
            "player_id": 100,
            "name": "Lionel Messi",
            "model_run_id": "run_test_001",
            "season": 2025,
            "market_value_eur": 25000000.0,
            "fair_value_eur": 45000000.0,
            "residual_log10": 0.255,
            "valuation_status": "undervalued",
            "is_undervalued": True,
            "rf_undervalued_prob": 0.82,
            "dt_undervalued_pred": True,
            "rf_undervalued_pred": True,
        },
        None,
    ]

    with patch(
        "delphos_backend.api.reports.generate_llm_report_text",
        new=AsyncMock(
            side_effect=HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LLM inference service unavailable",
            )
        ),
    ):
        response = await client.post("/reports/generate", json={"player_id": 100})

    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    problem = response.json()
    assert problem["status"] == 503
    assert "LLM inference service unavailable" in problem["detail"]


@pytest.mark.asyncio
async def test_list_and_get_reports(client: AsyncClient, mock_db: AsyncMock) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cur.fetchone.side_effect = [
        {"model_run_id": "run_test_001", "dataset_version": 679, "activated_at": None},
        {"model_run_id": "run_test_001", "dataset_version": 679, "activated_at": None},
        None,
    ]
    cur.fetchall.return_value = [
        {
            "id": 1,
            "player_id": 100,
            "player_name": "Lionel Messi",
            "model_run_id": "run_test_001",
            "report_type": "scouting",
            "content": "Report text.",
            "created_at": datetime(2026, 11, 7, 12, 0, tzinfo=UTC),
        }
    ]

    res_list = await client.get("/reports?player_id=100")
    assert res_list.status_code == 200
    assert res_list.json()["total"] == 1

    res_missing = await client.get("/reports/999")
    assert res_missing.status_code == 404
    assert res_missing.json()["detail"] == "Report not found"
