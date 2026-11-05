"""Unit tests for player search, profile, and valuation routes."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_players(client: AsyncClient, mock_db: AsyncMock) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    # 1. active model run
    # 2. count total
    # 3. fetch items
    cur.fetchone.side_effect = [
        {"model_run_id": "run_test_001", "dataset_version": 679, "activated_at": None},
        {"total": 1},
    ]
    cur.fetchall.return_value = [
        {
            "player_id": 100,
            "name": "Lionel Messi",
            "first_name": "Lionel",
            "last_name": "Messi",
            "position": "Attack",
            "sub_position": "Right Winger",
            "image_url": "http://img.png",
            "club_id": 1,
            "club_name": "Inter Miami",
            "market_value_eur": 25000000.0,
            "valuation_status": "undervalued",
            "cluster_id": 0,
        }
    ]

    response = await client.get("/players?page=1&page_size=10&cluster_id=0")
    assert response.status_code == 200
    data = response.json()
    assert data["model_run_id"] == "run_test_001"
    assert data["total"] == 1
    assert data["page"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Lionel Messi"
    assert data["items"][0]["valuation_status"] == "undervalued"
    assert data["items"][0]["cluster_name"] == "Attacking Creators & Scorers"


@pytest.mark.asyncio
async def test_get_player_profile_success(client: AsyncClient, mock_db: AsyncMock) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cur.fetchone.side_effect = [
        {"model_run_id": "run_test_001", "dataset_version": 679, "activated_at": None},
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
            "image_url": "http://img.png",
            "url": "http://tm.de/messi",
            "season": 2025,
            "as_of_date": "2025-06-01",
            "league_id": "MLS",
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
    ]

    response = await client.get("/players/100")
    assert response.status_code == 200
    data = response.json()
    assert data["model_run_id"] == "run_test_001"
    assert data["name"] == "Lionel Messi"
    assert data["active_season"]["goals"] == 15.0


@pytest.mark.asyncio
async def test_get_player_profile_not_found(client: AsyncClient, mock_db: AsyncMock) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cur.fetchone.side_effect = [
        {"model_run_id": "run_test_001", "dataset_version": 679, "activated_at": None},
        None,
    ]

    response = await client.get("/players/999999")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    data = response.json()
    assert data["title"] == "Not Found"
    assert data["status"] == 404
    assert data["detail"] == "Player not found"
    assert response.json()["detail"] == "Player not found"


@pytest.mark.asyncio
async def test_get_player_valuation_success(client: AsyncClient, mock_db: AsyncMock) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cur.fetchone.side_effect = [
        {"model_run_id": "run_test_001", "dataset_version": 679, "activated_at": None},
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
    ]

    response = await client.get("/players/100/valuation")
    assert response.status_code == 200
    data = response.json()
    assert data["is_undervalued"] is True
    assert data["rf_undervalued_prob"] == 0.82
