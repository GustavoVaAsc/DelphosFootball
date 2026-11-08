"""Unit tests for tactical replacement routes."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_replacements_success(client: AsyncClient, mock_db: AsyncMock) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cur.fetchone.side_effect = [
        {"model_run_id": "run_test_001", "dataset_version": 679, "activated_at": None},
        {
            "target_player_id": 200,
            "target_name": "Kylian Mbappé",
            "model_run_id": "run_test_001",
            "season": 2025,
            "is_elite_asset": True,
            "target_market_value_eur": 180000000.0,
            "qualifying_count": 3,
            "shortfall_reason": None,
        },
    ]
    cur.fetchall.return_value = [
        {
            "rank": 1,
            "candidate_player_id": 301,
            "candidate_name": "Bradley Barcola",
            "position": "Attack",
            "candidate_country_of_citizenship": "France",
            "candidate_image_url": "http://img-barcola.png",
            "candidate_club_id": 583,
            "candidate_club_name": "Paris Saint-Germain",
            "similarity_score": 0.94,
            "euclidean_distance": 0.32,
            "candidate_market_value_eur": 45000000.0,
            "cost_savings_eur": 135000000.0,
            "cost_ratio": 0.25,
            "candidate_fair_value_eur": 60000000.0,
            "candidate_valuation_status": "undervalued",
        }
    ]

    response = await client.get("/players/200/replacements")
    assert response.status_code == 200
    data = response.json()
    assert data["target_name"] == "Kylian Mbappé"
    assert data["is_elite_asset"] is True
    assert len(data["replacements"]) == 1
    assert data["replacements"][0]["cost_savings_eur"] == 135000000.0
    assert data["replacements"][0]["candidate_club_name"] == "Paris Saint-Germain"
    assert (
        data["replacements"][0]["candidate_club_logo_url"]
        == "https://tmssl.akamaized.net/images/wappen/head/583.png"
    )


@pytest.mark.asyncio
async def test_get_replacements_not_found(client: AsyncClient, mock_db: AsyncMock) -> None:
    cur = mock_db.cursor.return_value.__aenter__.return_value
    cur.fetchone.side_effect = [
        {"model_run_id": "run_test_001", "dataset_version": 679, "activated_at": None},
        None,
    ]

    response = await client.get("/players/999/replacements")
    assert response.status_code == 404
    assert "not evaluated as a replacement target" in response.json()["detail"]
